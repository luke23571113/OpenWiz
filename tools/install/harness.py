import os
from pathlib import Path
import re
import shlex
import shutil
import stat

import install as installer

HARNESSES = (('claude-code', '.claude', 'Claude Code'), ('codex', '.codex', 'Codex'),
             ('cursor', '.cursor', 'Cursor'), ('opencode', '.config/opencode', 'OpenCode'),
             ('grok', '.grok', 'Grok'))
MARK = '.openwiz-skill'
MARKED = re.compile(rb'openwiz\.skill-copy\.v1\n[0-9a-f]{40}\n')


def mark(source):
    return f'openwiz.skill-copy.v1\n{source}\n'.encode()


def owned_dir(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    installer.require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(),
                      f'{path} is a link or not your folder; nothing was changed')
    return True


def clash(folder, name, plain):
    target = folder / name
    if not ours(target):
        return (f'{target} is your own {name} skill, not an OpenWiz copy, so {plain} keeps it and does not get '
                f'OpenWiz\'s {name}. To use OpenWiz\'s, move or rename yours, then run this again.')
    for path in leftovers(folder, name):
        try:
            clear = ours(path)
        except installer.Refused:
            clear = False
        if not clear:
            return (f'{path} is in the way and OpenWiz did not make it, so {plain} does not get OpenWiz\'s {name}. '
                    'Look inside it, and if it holds nothing you want, remove it and run this again: '
                    f'rm -rf -- {shlex.quote(str(path))}')
    return None


def check(folder, names, plain):
    installer.path_guard(folder)
    if not owned_dir(folder):
        return []
    skipped = []
    for name in names:
        try:
            reason = clash(folder, name, plain)
        except installer.Refused as refusal:
            reason = f'{refusal}; {plain} does not get OpenWiz\'s {name}. Make it a real folder of yours, then run this again.'
        if reason:
            skipped.append({'skill': name, 'path': str(folder / name), 'next': reason})
    return skipped


def leftovers(folder, name):
    return folder / f'.openwiz-stage-{name}', folder / f'.openwiz-old-{name}'


def ours(path):
    if not owned_dir(path):
        return True
    try:
        fd = os.open(path / MARK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        text = os.read(fd, 64) if stat.S_ISREG(os.fstat(fd).st_mode) else b''
    finally:
        os.close(fd)
    return MARKED.fullmatch(text) is not None


def place(folder, skills, names, source):
    folder.mkdir(mode=0o700, exist_ok=True)
    for name in names:
        (stage, old), target = leftovers(folder, name), folder / name
        for leftover in (stage, old):
            if owned_dir(leftover):
                shutil.rmtree(leftover)
        stage.mkdir(mode=0o700)
        fd = os.open(stage / MARK, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(mark(source))
        for path in sorted((skills / name).rglob('*')):
            if path.is_dir() or path == skills / name / MARK:
                continue
            copy = stage / path.relative_to(skills / name)
            copy.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         stat.S_IMODE(path.lstat().st_mode))
            with os.fdopen(fd, 'wb') as handle:
                handle.write(path.read_bytes())
        if owned_dir(target):
            os.rename(target, old)
        os.rename(stage, target)
        if owned_dir(old):
            shutil.rmtree(old)


def guard_parent(base, plain):
    try:
        installer.path_guard(base.parent)
    except installer.Refused:
        culprit = next((p for p in (base.parent, *base.parent.parents)
                        if p.is_symlink() or (p.exists() and not p.is_dir())), base.parent)
        raise installer.Refused(f'{culprit} is a link or not a folder, so OpenWiz will not write {plain}\'s skills '
                                f'through it; nothing was changed. Make {culprit} a real folder, or move {base} away '
                                f'if you don\'t use {plain}, then run this again.') from None


def unreadable(path, plain, error):
    culprit = next((p for p in reversed((path, *path.parents)) if not os.access(p, os.X_OK)), path.parent)
    return (f'OpenWiz could not look inside {culprit} ({error.strerror}), so it cannot tell what is in {plain}\'s '
            f'folder; nothing was changed. Give yourself access with chmod u+rx -- {shlex.quote(str(culprit))}, '
            'then run this again.')


def install_skills(build, value, root, home, codex_home=None, release=None, skills_from=None):
    skills = release or build / 'runtime/skills'
    if release is None:
        installer.private(skills)
    names = sorted(p.name for p in skills.iterdir() if p.is_dir() and not p.is_symlink())
    installer.require(names, 'the selected build ships no skills')
    canonical = Path(root) / 'skills'
    rows, plan = [], []
    for harness, relative, plain in HARNESSES:
        base = Path(codex_home) if harness == 'codex' and codex_home else Path(home) / relative
        row = {'id': harness, 'path': str(base / 'skills')}
        try:
            installer.require(base.is_absolute(), f'{base} is not an absolute folder')
            try:
                present = owned_dir(base)
            except NotADirectoryError:
                present = False
            if not present:
                row.update(state='absent', next=f'{plain} is not set up here ({base} is missing), so it got no '
                                                f'skills; install {plain}, then run this again.')
            else:
                guard_parent(base, plain)
                skipped = check(base / 'skills', names, plain)
                wanted = [n for n in names if n not in {s['skill'] for s in skipped}]
                if wanted:
                    plan.append((base / 'skills', wanted))
                row.update(state='partial' if skipped and wanted else 'refused' if skipped else 'installed',
                           next=f'{plain} finds these skills next time it starts.' if not skipped else
                           f'{plain} did not get {len(skipped)} skill(s); each one below says why and what to do.')
                if skipped:
                    row['skipped'] = skipped
        except installer.Refused as refusal:
            row.update(state='refused', next=str(refusal))
        except OSError as error:
            row.update(state='refused', next=unreadable(Path(error.filename or base), plain, error))
        rows.append(row)
    result = {'schema': 'openwiz.skills-install.v1', 'version': value['version'], 'source': value['source'],
              'skills_from': skills_from or {'kind': 'bundled', 'reason': 'The installed build\'s own skills.'},
              'canonical': str(canonical), 'skills': names, 'harnesses': rows}
    if not plan:
        return dict(result, outcome='refused', reason='No agent here can take OpenWiz\'s skills (see each row); '
                                                      'nothing was changed.'), 5
    try:
        skipped = check(canonical, names, 'OpenWiz\'s own skills folder')
    except installer.Refused as refusal:
        return dict(result, outcome='refused', reason=str(refusal) + '; nothing was changed.'), 5
    if skipped:
        result['canonical_skipped'] = skipped
    plan.insert(0, (canonical, [n for n in names if n not in {s['skill'] for s in skipped}]))
    for folder, wanted in plan:
        place(folder, skills, wanted, value['source'])
    whole = not skipped and all(row['state'] in ('installed', 'absent') for row in rows)
    return dict(result, outcome='installed' if whole else 'partial',
                reason='Copied the skills into every agent here.' if whole else
                'Copied the skills where it was safe; the rows say what was skipped and why.'), 0

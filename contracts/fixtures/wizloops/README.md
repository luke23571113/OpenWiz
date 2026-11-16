# Pinned WizLoops format (v1)

This folder and three files beside it are an exact copy of the WizLoops
loop file format. They are pinned from `openwizdev/WizLoops` at commit
`3847b375cbbf6ab0e88b0f643fa5a4e943183b03`, the WL1 merge (WizLoops pull
request 11). WizLoops owns the format and the Cloudroom adapter rules;
OpenWiz owns the code that reads and applies them. OpenWiz never edits
these files in place: it changes them only by pinning a later WizLoops
commit, and replaces this record in the same change.

| Pinned here | WizLoops path at that commit |
| --- | --- |
| [`contracts/wizloops-loop.v1.md`](../../wizloops-loop.v1.md) | `format/loop.v1.md` |
| [`contracts/wizloops-loop.v1.schema.json`](../../wizloops-loop.v1.schema.json) | `format/loop.v1.schema.json` |
| [`contracts/wizloops-cloudroom.v1.md`](../../wizloops-cloudroom.v1.md) | `adapters/cloudroom.v1.md` |
| `contracts/fixtures/wizloops/` (everything but this README) | `format/fixtures/` |

The pinned files keep their relative links as WizLoops wrote them. In
`wizloops-loop.v1.md`, `loop.v1.schema.json` means
`wizloops-loop.v1.schema.json` here, and `fixtures/` means this folder. In
`wizloops-cloudroom.v1.md`, `../format/loop.v1.md` means
`wizloops-loop.v1.md`, and `../format/fixtures/valid/` means `valid/` here.
The check scripts keep their executable mode. `invalid/crlf.md` keeps its
carriage returns: it is the format's `encoding` fixture.

## Byte-for-byte record

The SHA-256 of every pinned file was taken from the WizLoops checkout at
that commit. To check it from the repository's root, run
`sed -n '/^```sha256/,/^```$/p' contracts/fixtures/wizloops/README.md | sed '1d;$d' | sha256sum -c`.
The CLI's tests (`crates/cli/src/loop_files.rs`) read this block and check
that it covers every file here, with none missing or extra.

```sha256
74ad620b70d98c92bc14d3bff2967dbc12235f8fd2522f31020be4431cb619f6  contracts/wizloops-loop.v1.md
721296695db400d28d649c4562b4f633ddc28990c199fb2515fa2733e67a0bdc  contracts/wizloops-loop.v1.schema.json
b370d91a74ef6ce27ba7ba7a850236247420522975bce446676de67fa48b54d0  contracts/wizloops-cloudroom.v1.md
484ea03b955240a16dc8934857de26c3e153bc2a3a2b63472ce56241d92ecf67  contracts/fixtures/wizloops/catalog/all-secrets.md
02a4a979354a5579c9569f358b0904d58dc3b0faf1e03d960a9865e07baae280  contracts/fixtures/wizloops/expected.json
d0be86b4569fb8ec34d3eaebea9a6ea0ecaed89edfb681984fa9340feb6af90b  contracts/fixtures/wizloops/invalid-folder/duplicate-id/a.md
d0be86b4569fb8ec34d3eaebea9a6ea0ecaed89edfb681984fa9340feb6af90b  contracts/fixtures/wizloops/invalid-folder/duplicate-id/b.md
23dc80f932e5d8f6d20f5b7052cc062bd159022865b5acf0a043aece88007f55  contracts/fixtures/wizloops/invalid/agent-space.md
3ccdf42d627fe96e766db0a7a23f5514ae68b8620cf4b4a7bba3be712a4d7a14  contracts/fixtures/wizloops/invalid/at-no-offset.md
0f0791e2004513fedb43a4f2d3532de6f7d0c947768a0a04452f74dac54fa6ea  contracts/fixtures/wizloops/invalid/bad-id.md
3cf2ff8fe840958a67ebd6ae02ebecb9d522838396615e9242217416cd0f0042  contracts/fixtures/wizloops/invalid/bad-param-name.md
65c293823609d754942ea2f2bef59bc22c0e9dcd4a5324f90381830a59e98369  contracts/fixtures/wizloops/invalid/bad-placeholder.md
569b8f442ea6c0032f7f6ef2fc0adf7ce4484ab390e01a068a42ed914d1c174b  contracts/fixtures/wizloops/invalid/bad-thread.md
df8e7bac63026e63e4daf702274c7c330c95f5ddf81ae21d90e4d08371ad78db  contracts/fixtures/wizloops/invalid/bad-timezone.md
e64f1dfaa2651ce6f01a0b4381592b465280a1b406e27e23e20d5fc13a229b96  contracts/fixtures/wizloops/invalid/blank-line.md
7557b95e724d19812bfe15aca0c36a73d81394b0df8513d1e525e9ff95944830  contracts/fixtures/wizloops/invalid/blank-name.md
04aaba265d4bdf6b5f8e7652d648f4029899562d57b73045d771b05246a5d7eb  contracts/fixtures/wizloops/invalid/check-missing.md
af0b724b092355099d930cb2fd88e455ec32f04bf935affebcff3652f3b7ff5b  contracts/fixtures/wizloops/invalid/check-parent.md
9082908834f8d9e20e2a9bc6ec557a6ca734db552338fc497c15c76a46033bd6  contracts/fixtures/wizloops/invalid/comment-line.md
e2ff08c32dca0fd338329aff6c6f1bb666adae35e95bdd0aa8485cb4f8204301  contracts/fixtures/wizloops/invalid/crlf.md
b64d6e78386dec19c075f6b8d0930d4346aea9d362fbeb6d0b1e40486ba233ad  contracts/fixtures/wizloops/invalid/cron-names.md
7d558640670448b9484bc1bdb774052fe3d96a7e58e44aa629ef8630e844919e  contracts/fixtures/wizloops/invalid/cron-out-of-range.md
aee4754288228e461e7e7c7a1bf81c465fc51c7d9ab9ed909bd3fb0a42abe28c  contracts/fixtures/wizloops/invalid/cron-six-fields.md
b93480e07a9213d7f992271cbd226677d491f815a4bc9184c2797cf352a7bd90  contracts/fixtures/wizloops/invalid/duplicate-key.md
e907e3e6d48180fd197beba7774cbcf15c85d5188b14578e2842a2e6d768d891  contracts/fixtures/wizloops/invalid/duplicate-nested-key.md
f3d6759f2129046198f8ef03f9aefb65570f1d39828009f521e9bb94e957b6fb  contracts/fixtures/wizloops/invalid/duplicate-secret.md
11c9f6938ba8240a192402ce4bbb0a68ca92748728428727645a44ed3e54d47f  contracts/fixtures/wizloops/invalid/empty-body.md
59e4342591f944b78cd7514c94e06b08b51d2abd54d86bc9a1bae7bbf80e7a07  contracts/fixtures/wizloops/invalid/in-seconds.md
54c9a778d5a0c963f6bbbb51b630da6ac9856431de10bcb8d2f325ca5c1d6075  contracts/fixtures/wizloops/invalid/missing-thread.md
b7259aa30a5a5883afbe96a5c145198fb8569e48bf328dbaaf49bd470d62ded1  contracts/fixtures/wizloops/invalid/missing-timezone.md
1e3bc249b57cdb7dff0a9e8d67303f202844db1e5b9ff50cac54f28ecf64087c  contracts/fixtures/wizloops/invalid/no-frontmatter.md
b353b774c9431f644effc91805971f20aab4f4f2d1dfb2b6bd900e9846720705  contracts/fixtures/wizloops/invalid/no-space.md
fe919c2cb2ab76da361ba7d32444a5167c5333b9a8fce41884cd770a7b70c0f7  contracts/fixtures/wizloops/invalid/null-check.md
90cafdae1b99598037f7d347c4f22abc086f586fe5126233ea3ce98a058a8f88  contracts/fixtures/wizloops/invalid/param-float.md
72a031a29f81dc9fcb0fe9e6926339d6ab6b3e26567d76ccf5da62e2974f6ced  contracts/fixtures/wizloops/invalid/priority-five.md
0aa768938d973bb3c5072d0ec41b5b764399dc7197ea48a8c7902177a6908d8e  contracts/fixtures/wizloops/invalid/priority-float.md
8bc57eac32573faac0b0a301f6e359cc5f43c5eb2460e4c7d3886672cd4c14da  contracts/fixtures/wizloops/invalid/priority-string.md
2f8f90273e2e746cddbb65d1bef7b6fd01264caae55dfef8f7e016f2a9fb982f  contracts/fixtures/wizloops/invalid/same-thread-secrets.md
c9d437ffcdf5f5e173b9e940ee4fc27fd5ed63b14e258ed0440371a7b2d86c1e  contracts/fixtures/wizloops/invalid/secrets-all.md
25761f4bcec7ce9c6ee6685d95943cfa2d39064269dc875b6896d3b4d3597aff  contracts/fixtures/wizloops/invalid/secrets-none-string.md
47674f5b0202dbbd79da7c86ab67296dc0b83f2d45ba9a3ee54ee6e213fb7ceb  contracts/fixtures/wizloops/invalid/timeout-too-long.md
3c632f8ba31411dcf35c53d8aeb402e649bb76b00ec5d9eb05f3976edca9d3bb  contracts/fixtures/wizloops/invalid/timeout-too-long/check.sh
6b228a38e907078bb0bc5a9159260a15ac32b105b213f0e7d753cdf446ab1781  contracts/fixtures/wizloops/invalid/timezone-only.md
a2c34fb36b89e4c6c53f3b3d2eb94c7d35b09fabac2ac86b5483f49563f6b161  contracts/fixtures/wizloops/invalid/two-triggers.md
0da754c7b7760b492adb3755724e35af4933bddf2e10416b72a0563d23313c90  contracts/fixtures/wizloops/invalid/unclosed.md
d62b2f94834bf7eea7615b8fef33b5b8a3af6e922e5957826ad457c47add8ac9  contracts/fixtures/wizloops/invalid/undeclared-param-check.md
ba976056f94cc42774c79340e3739cbf26a4bfbd71037c0e6c1fe3f0cfb9c839  contracts/fixtures/wizloops/invalid/undeclared-param-check/check.sh
73386819718257847aa1496bb05e04415c37f26bc75b239074b0bbc680c61841  contracts/fixtures/wizloops/invalid/undeclared-param.md
43fdcd34c972c5d0f9bbc69043e17709c0d993525bcc9ed6da029b8e0860f622  contracts/fixtures/wizloops/invalid/unknown-agent-key.md
85cda9c6355dd3a75e14fae3edbdf42e34bcfa549d40ca28140cb10d760a0870  contracts/fixtures/wizloops/invalid/unknown-field.md
03c25f79ff0659ecf64805ab271dcb861166e235a5ed46fcce3256864abc861f  contracts/fixtures/wizloops/invalid/unquoted-string.md
00004221946eca94466d51c792be8992ff90188754c65f25ba4453cc32599218  contracts/fixtures/wizloops/invalid/unused-param.md
6ef71b04872c40847b4578918005b3f7caf419ae9f48ec74a575200e0aaac684  contracts/fixtures/wizloops/invalid/webhook-false.md
7d766e433c1374217cd1fc7392fa56faf8dfe3deeaf43261f4d050a24d6cf2e9  contracts/fixtures/wizloops/valid/all-secrets-new.md
250b71d207572f7631668c083c974cb01db0815333064d42cf346ddbf56a43cc  contracts/fixtures/wizloops/valid/all-secrets-same.md
0f88715372bbe4d355f12a816316935a0e38fbf266dd212942bb2396fcae93a3  contracts/fixtures/wizloops/valid/at-same.md
cda822c3a2a7d03fcb229f149e6dec3558a8ef7d17acd73851299c9c9278d177  contracts/fixtures/wizloops/valid/cron-check.md
01bfb2744e54a80ee90e4cf95a25b1f36972d7458685b5b4cd9c43ed147f7b57  contracts/fixtures/wizloops/valid/cron-check/check.sh
b5cd05aa5e70b48604f872fddedeaf14416f245158a28c6c94fccb13d0981eca  contracts/fixtures/wizloops/valid/fast-no-check.md
5eff4ca38129f0f6238864ce97917d9a4561e761b62e5dfac29c028daaa7e011  contracts/fixtures/wizloops/valid/in-same.md
5153c2756c196167eb1b6d87f0b79003f87fb46113dfd10a94dcecba529a1a9c  contracts/fixtures/wizloops/valid/long-check.md
3c632f8ba31411dcf35c53d8aeb402e649bb76b00ec5d9eb05f3976edca9d3bb  contracts/fixtures/wizloops/valid/long-check/check.sh
659a637362376dfc1af53a31e6dda5d6733005dda371f1ea18e3323696a1f56f  contracts/fixtures/wizloops/valid/same-thread-agent.md
3c632f8ba31411dcf35c53d8aeb402e649bb76b00ec5d9eb05f3976edca9d3bb  contracts/fixtures/wizloops/valid/same-thread-agent/check.sh
6cf72fe9e18007672c03b198da7e7113c9d892dfd16ddb4dc6215f11d2f453a0  contracts/fixtures/wizloops/valid/script-only.md
09fe0ef81e9c468f1b88cfd2c4561e75106a16459f6aa333b5014155632ea51f  contracts/fixtures/wizloops/valid/script-only/check.sh
1ba6b804d14a45799f4c69233b55b5f2b9788cb574759bedcab75258330ba546  contracts/fixtures/wizloops/valid/short-check.md
3c632f8ba31411dcf35c53d8aeb402e649bb76b00ec5d9eb05f3976edca9d3bb  contracts/fixtures/wizloops/valid/short-check/check.sh
b4852d94b416aa69647f18f513eb616ad9d2d62009773ebc04cbbd2373f8ad96  contracts/fixtures/wizloops/valid/webhook-new.md
```

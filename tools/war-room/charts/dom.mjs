// WRD2 (#630): the smallest DOM Observable Plot needs to draw at build time, and an XML
// serializer for what it draws. Build only: nothing here reaches the page. It supports
// elements, attributes, text, fragments and simple tag/class selectors; anything else
// throws, so a Plot feature outside this subset fails the build instead of drawing wrong.
const XHTML = 'http://www.w3.org/1999/xhtml';

class Node_ {
  constructor(doc) { this.ownerDocument = doc; this.childNodes = []; this.parentNode = null; }
  get firstChild() { return this.childNodes[0] ?? null; }
  get lastChild() { return this.childNodes.at(-1) ?? null; }
  get nextSibling() { return this.parentNode?.childNodes[this.parentNode.childNodes.indexOf(this) + 1] ?? null; }
  get previousSibling() {
    const i = this.parentNode ? this.parentNode.childNodes.indexOf(this) : -1;
    return i > 0 ? this.parentNode.childNodes[i - 1] : null;
  }
  appendChild(child) { return this.insertBefore(child, null); }
  insertBefore(child, ref) {
    if (child.nodeType === 11) { for (const c of [...child.childNodes]) this.insertBefore(c, ref); return child; }
    child.parentNode?.removeChild(child);
    const i = ref == null ? this.childNodes.length : this.childNodes.indexOf(ref);
    if (i < 0) throw new Error('insertBefore: not a child');
    this.childNodes.splice(i, 0, child);
    child.parentNode = this;
    return child;
  }
  removeChild(child) {
    const i = this.childNodes.indexOf(child);
    if (i < 0) throw new Error('removeChild: not a child');
    this.childNodes.splice(i, 1);
    child.parentNode = null;
    return child;
  }
  remove() { this.parentNode?.removeChild(this); }
  append(...items) { for (const x of items) this.appendChild(typeof x === 'string' ? this.ownerDocument.createTextNode(x) : x); }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(''); }
  set textContent(value) {
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes = [];
    if (value != null && value !== '') this.appendChild(this.ownerDocument.createTextNode(String(value)));
  }
}

class Text_ extends Node_ {
  constructor(doc, data) { super(doc); this.nodeType = 3; this.data = data; }
  get textContent() { return this.data; }
  set textContent(value) { this.data = String(value); }
}

class Fragment_ extends Node_ {
  constructor(doc) { super(doc); this.nodeType = 11; }
}

class Element_ extends Node_ {
  constructor(doc, ns, name) {
    super(doc);
    this.nodeType = 1;
    this.namespaceURI = ns;
    this.tagName = this.localName = name;
    this.attributes_ = new Map();
    const self = this;
    const style = {
      setProperty(k, v) { self.setStyle(k, v); },
      removeProperty(k) { self.setStyle(k, null); },
      getPropertyValue(k) { return self.styles()[k] ?? ''; },
    };
    this.style = new Proxy(style, {
      set(_, k, v) { self.setStyle(String(k).replace(/[A-Z]/g, (m) => '-' + m.toLowerCase()), v); return true; },
      get(t, k) { return k in t ? t[k] : (self.styles()[k] ?? ''); },
    });
  }
  styles() {
    const out = {};
    for (const part of (this.attributes_.get('style') ?? '').split(';')) {
      const i = part.indexOf(':');
      if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
    }
    return out;
  }
  setStyle(k, v) {
    const all = this.styles();
    if (v == null || v === '') delete all[k]; else all[k] = String(v);
    const text = Object.entries(all).map(([a, b]) => `${a}: ${b};`).join(' ');
    if (text) this.attributes_.set('style', text); else this.attributes_.delete('style');
  }
  setAttribute(k, v) { this.attributes_.set(k, String(v)); }
  setAttributeNS(_, k, v) { this.attributes_.set(k, String(v)); }
  getAttribute(k) { return this.attributes_.has(k) ? this.attributes_.get(k) : null; }
  hasAttribute(k) { return this.attributes_.has(k); }
  removeAttribute(k) { this.attributes_.delete(k); }
  removeAttributeNS(_, k) { this.attributes_.delete(k); }
  get children() { return this.childNodes.filter((c) => c.nodeType === 1); }
  get firstElementChild() { return this.children[0] ?? null; }
  get classList() {
    const names = () => (this.getAttribute('class') ?? '').split(/\s+/).filter(Boolean);
    return {
      add: (...c) => this.setAttribute('class', [...new Set([...names(), ...c])].join(' ')),
      remove: (...c) => this.setAttribute('class', names().filter((x) => !c.includes(x)).join(' ')),
      contains: (c) => names().includes(c),
    };
  }
  matches(selector) { return selector.split(',').some((s) => matchOne(this, s.trim())); }
  querySelectorAll(selector) {
    const found = [];
    const walk = (node) => { for (const c of node.children) { if (c.matches(selector)) found.push(c); walk(c); } };
    walk(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}

function matchOne(element, selector) {
  if (selector === '*') return true;
  const m = /^([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)$/.exec(selector);
  if (!m) throw new Error('build DOM: unsupported selector');
  if (m[1] && element.localName !== m[1]) return false;
  const names = (element.getAttribute('class') ?? '').split(/\s+/);
  return m[2].split('.').filter(Boolean).every((c) => names.includes(c));
}

export class BuildDocument extends Node_ {
  constructor() {
    super(null);
    this.ownerDocument = this;
    this.nodeType = 9;
    this.documentElement = new Element_(this, XHTML, 'html');
    this.defaultView = null;
  }
  createElementNS(ns, name) { return new Element_(this, ns, name); }
  createElement(name) { return new Element_(this, XHTML, name); }
  createTextNode(text) { return new Text_(this, String(text)); }
  createDocumentFragment() { return new Fragment_(this); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
}

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export function serialize(node) {
  if (node.nodeType === 3) return escape(node.data);
  if (node.nodeType !== 1) throw new Error('build DOM: unexpected node');
  const attributes = [...node.attributes_].map(([k, v]) => ` ${k}="${escape(v)}"`).join('');
  return `<${node.tagName}${attributes}>${node.childNodes.map(serialize).join('')}</${node.tagName}>`;
}

const BASE = new URL('../war-room/', import.meta.url);
const { READ } = await import(new URL('reader.mjs', BASE).href);
const spec = '../war-room/harness.mjs';
const harness = await import(spec);
console.log(READ, harness.NAME);

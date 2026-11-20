// SPDX-License-Identifier: MIT
const url = "https://example.com/#x"; // the url
const re = /\/\/ not a comment/g;
const half = 4 / 2; // halve it
const tpl = `a ${ {b: 1}.b } // not a comment ${'/* nor this */'}`;
/**
 * Adds two numbers.
 */
export function add(a, b) {
  return a + b;
}
// eslint-disable-next-line no-console -- the synthetic page logs on purpose
console.log(add(1, 2));
/* eslint-disable no-alert */
alert(half);
// SECURITY: never put a token in the url.
// Private record: https://github.com/jparker2006/ClosedWiz/pull/9002#issuecomment-9000000002
export const done = true;

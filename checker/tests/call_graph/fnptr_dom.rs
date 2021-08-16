// Copyright (c) Facebook, Inc. and its affiliates.
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.
//

// Linear call graph with function pointer calls, single type, dominance, no loops.

fn fn1(x: u32, fn2: &fn(u32) -> u32, fn3: &fn(u32) -> u32) -> u32 {
    let y = fn2(x);
    fn3(y)
}
fn fn2(x: u32) -> u32 {
    x + 2
}
fn fn3(x: u32) -> u32 {
    x + 3
}
pub fn main() {
    let x = 1;
    fn1(x, &(fn2 as fn(u32) -> u32), &(fn3 as fn(u32) -> u32));
}

/* CONFIG
{
    "reductions": [],
    "included_crates": []
}
*/

/* EXPECTED:DOT
digraph {
    0 [ label = "\"fnptr_dom[8787]::main\"" ]
    1 [ label = "\"fnptr_dom[8787]::fn1\"" ]
    2 [ label = "\"fnptr_dom[8787]::fn2\"" ]
    3 [ label = "\"fnptr_dom[8787]::fn3\"" ]
    0 -> 1 [ ]
    0 -> 1 [ ]
    1 -> 2 [ ]
    1 -> 3 [ ]
}
*/

/* EXPECTED:DDLOG
start;
Dom(2,3);
Edge(0,0,1);
Edge(1,0,1);
Edge(2,1,2);
Edge(3,1,3);
EdgeType(0,0);
EdgeType(1,1);
EdgeType(2,0);
EdgeType(3,0);
commit;
*/

/* EXPECTED:TYPEMAP
{
  "0": "u32",
  "1": "&fn(u32) -> u32"
}
*/

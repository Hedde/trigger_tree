#!/usr/bin/env node
"use strict";

const value = process.argv[2] || "";
const colors = value.split(",").map((hex) => hex.trim());
if (colors.length < 2 || colors.some((hex) => !/^#[0-9a-f]{6}$/i.test(hex))) {
  console.error("usage: validate_palette.js '#hex,#hex,…' --mode dark");
  process.exit(2);
}

const rgb = (hex) => [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255);
const simulations = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protan: [[0.567, 0.433, 0], [0.558, 0.442, 0], [0, 0.242, 0.758]],
  deutan: [[0.625, 0.375, 0], [0.7, 0.3, 0], [0, 0.3, 0.7]],
  tritan: [[0.95, 0.05, 0], [0, 0.433, 0.567], [0, 0.475, 0.525]],
};
const transform = (color, matrix) => matrix.map((row) => row.reduce((sum, n, i) => sum + n * color[i], 0));
const distance = (a, b) => Math.sqrt(a.reduce((sum, n, i) => sum + (n - b[i]) ** 2, 0)) * 255;
let failed = false;
for (let index = 1; index < colors.length; index += 1) {
  const scores = Object.entries(simulations).map(([name, matrix]) => [name, distance(transform(rgb(colors[index - 1]), matrix), transform(rgb(colors[index]), matrix))]);
  const minimum = Math.min(...scores.map(([, score]) => score));
  console.log(`${colors[index - 1]} → ${colors[index]}: ${scores.map(([name, score]) => `${name} ${score.toFixed(1)}`).join(" · ")}`);
  if (minimum < 28) failed = true;
}
console.log(failed ? "FAIL: adjacent step below CVD separation threshold 28" : "PASS: all adjacent steps meet CVD separation threshold 28");
process.exitCode = failed ? 1 : 0;

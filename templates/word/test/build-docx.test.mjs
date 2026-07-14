// node --test: build-docx.js produces a valid DOCX with the expected headings.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, "..", "build-docx.js");

/** Extract one file from a zip buffer (local-file-header walk, deflate or stored). */
function unzipEntry(buffer, wantedName) {
  let offset = 0;
  while (offset < buffer.length - 4) {
    if (buffer.readUInt32LE(offset) !== 0x04034b50) break; // local file header magic
    const method = buffer.readUInt16LE(offset + 8);
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const nameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const name = buffer.toString("utf-8", offset + 30, offset + 30 + nameLength);
    const dataStart = offset + 30 + nameLength + extraLength;
    const data = buffer.subarray(dataStart, dataStart + compressedSize);
    if (name === wantedName) {
      return method === 8 ? zlib.inflateRawSync(data).toString("utf-8") : data.toString("utf-8");
    }
    offset = dataStart + compressedSize;
  }
  return null;
}

test("build-docx generates a valid IMRaD docx", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "builddocx-"));
  const sections = path.join(dir, "sections");
  fs.mkdirSync(sections);
  fs.writeFileSync(path.join(dir, "config.yaml"), [
    'title: "A Test Manuscript"',
    "authors:",
    '  - name: "Jane Doe"',
    '  - name: "Rick Roe"',
    'journal: "Journal of Tests"',
  ].join("\n"));
  fs.writeFileSync(path.join(sections, "abstract.md"), "A short **abstract** with *emphasis*.");
  fs.writeFileSync(path.join(sections, "introduction.md"),
    "Opening paragraph.\n\n## Background\n\n- first point\n- second point");
  fs.writeFileSync(path.join(sections, "methods.md"), "We used `build-docx.js` for this test.");

  const out = path.join(dir, "paper.docx");
  const stdout = execFileSync(process.execPath, [SCRIPT, "--manuscript", dir, "--out", out], {
    encoding: "utf-8",
  });
  assert.match(stdout, /Wrote .*paper\.docx/);

  const buffer = fs.readFileSync(out);
  assert.equal(buffer.readUInt16BE(0), 0x504b, "output is not a zip (PK magic missing)");

  const xml = unzipEntry(buffer, "word/document.xml");
  assert.ok(xml, "word/document.xml not found in the docx");
  assert.match(xml, /A Test Manuscript/);
  assert.match(xml, /Jane Doe, Rick Roe/);
  assert.match(xml, /Abstract/);
  assert.match(xml, /1\. Introduction/, "Introduction should be numbered");
  assert.match(xml, /1\.1 Background/, "H2 should carry hierarchical numbering");
  assert.match(xml, /2\. Methods/, "Methods should continue the numbering");
});

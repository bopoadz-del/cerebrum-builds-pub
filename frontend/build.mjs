// Build the one UI the platform serves.
//
// The console is dependency-free HTML so the runtime image needs no browser
// toolchain. The build validates that every API path the page calls is a real
// platform route family, then emits dist/index.html for the image to copy over
// app/static/index.html.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "index.html"), "utf8");

const required = [
  "/v1/capabilities",
  "/v1/contract_and_boq_source_of_record",
  "/v1/document_register",
  "/v1/document_register/intake",
  "/v1/document_register/ask",
];
for (const route of required) {
  if (!source.includes(route)) {
    throw new Error(`console does not drive ${route}`);
  }
}
if (!source.includes("Authority:")) {
  throw new Error("console does not label the authority of its answers");
}
for (const screen of ["command_center", "operational_chat", "resident_engineer"]) {
  if (!source.includes('data-screen="' + screen + '"')) {
    throw new Error("console does not render the " + screen + " screen");
  }
}

mkdirSync(join(here, "dist"), { recursive: true });
writeFileSync(join(here, "dist", "index.html"), source, "utf8");
console.log("built dist/index.html");

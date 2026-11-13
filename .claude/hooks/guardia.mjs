// Hook PreToolUse del proyecto (Write|Edit|Read).
// Lee el JSON del hook por stdin y, si procede, deniega la llamada explicando el motivo.
//  - Write/Edit: deniega si el texto a escribir menciona el VAE de FLUX.2-dev (licencia no comercial).
//  - Read: deniega la lectura del archivo de variables de entorno (.env).
// El patrón se arma con escapes para que este archivo no contenga la cadena literal.
import { basename } from "node:path";

const PATRON_MODELO_NO_COMERCIAL = /FLUX\.2[-_ ]?dev/i;

function denegar(motivo) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: motivo,
      },
    }),
  );
  process.exit(0);
}

let entrada = "";
for await (const trozo of process.stdin) entrada += trozo;

let datos;
try {
  datos = JSON.parse(entrada);
} catch {
  process.exit(0); // sin JSON válido no hay nada que evaluar
}

const herramienta = datos.tool_name;
const args = datos.tool_input ?? {};

if (herramienta === "Write" || herramienta === "Edit") {
  const texto = herramienta === "Write" ? args.content : args.new_string;
  if (typeof texto === "string" && PATRON_MODELO_NO_COMERCIAL.test(texto)) {
    denegar(
      "Bloqueado: el texto menciona el modelo de imagen FLUX.2-dev, cuya licencia es " +
        "NO comercial y que el plan de Vitrina descarta. Idol debe usar el VAE de " +
        "black-forest-labs/FLUX.2-klein-4B (Apache 2.0). Corrige el texto y vuelve a intentarlo; " +
        "si de verdad hace falta nombrarlo (p. ej. en documentación), pide al usuario que lo escriba.",
    );
  }
}

if (herramienta === "Read") {
  const nombre = basename(String(args.file_path ?? "")).toLowerCase();
  const esEnv = nombre === ".env" || (nombre.startsWith(".env.") && nombre !== ".env.example");
  if (esEnv) {
    denegar(
      "Bloqueado: el archivo de variables de entorno (.env) contiene secretos y las reglas " +
        "del proyecto prohíben leerlo, editarlo, moverlo o borrarlo. Si necesitas saber qué " +
        "variables existen, pregunta al usuario o consulta la documentación.",
    );
  }
}

process.exit(0);

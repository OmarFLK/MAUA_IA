"""Generate SEMOB-only credentials offline; never prints either credential."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets


def generate_credentials() -> dict:
    key = "maua_semob_" + secrets.token_urlsafe(48)
    return {
        "maua_ia": {"SEMOB_INTEGRATION_KEY_SHA256": hashlib.sha256(key.encode()).hexdigest()},
        "semob": {
            "SEMOB_AI_URL": "https://cmob-ai-backend.onrender.com/api/integrations/semob/chat",
            "SEMOB_AI_API_KEY": key,
            "SEMOB_AI_REQUEST_FIELD": "message",
            "SEMOB_AI_RESPONSE_FIELD": "answer",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Private file outside the repository. Existing files are never overwritten.")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(repo):
        parser.error("Escolha um caminho fora do repositório para proteger a chave.")
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(generate_credentials(), output, indent=2)
    print("Credencial exclusiva do SEMOB gerada no arquivo privado. Nenhum segredo foi exibido.")


if __name__ == "__main__":
    main()

PYTHON ?= python3
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: check verify-payload smoke test

check: verify-payload smoke test

verify-payload:
	$(PYTHON) -c 'import hashlib,json,pathlib,sys; root=pathlib.Path.cwd(); spec=json.loads((root/"bundle-manifest.json").read_text()); names=(root/"bundle-files.txt").read_text().splitlines(); expected=spec["files"]; valid_names=len(names)==len(set(names))==8 and set(names)==set(expected) and all(not pathlib.PurePosixPath(n).is_absolute() and all(p not in ("", ".", "..") for p in n.split("/")) for n in names); valid_names or sys.exit("Invalid bundle file list"); spec["version"]==(root/"VERSION").read_text().strip() or sys.exit("Version mismatch"); bad=[n for n in names if any((root.joinpath(*pathlib.PurePosixPath(n).parts[:i])).is_symlink() for i in range(1,len(pathlib.PurePosixPath(n).parts)+1)) or not (root/n).is_file() or hashlib.sha256((root/n).read_bytes()).hexdigest()!=expected[n]]; not bad or sys.exit("Payload drift: "+", ".join(bad)); print("Payload verified: 8 files, "+spec["version"])'

smoke:
	$(PYTHON) scripts/session_binding.py --help > /dev/null
	$(PYTHON) scripts/task_packet.py --help > /dev/null

test:
	$(PYTHON) -m unittest discover -s scripts/tests -v

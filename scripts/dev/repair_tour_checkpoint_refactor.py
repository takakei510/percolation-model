#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("apply_tour_checkpoint_refactor.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    perm_c,
    "            fclose(main_fp);\\n"
    "            tour_buffer_destroy(&buffer);",
    "            if (convergence_fp) fclose(convergence_fp);\\n"
    "            fclose(main_fp);\\n"
    "            tour_buffer_destroy(&buffer);",
)
'''
new = '''replace_once(
    perm_c,
    "        if (!tours_fp) {\\n"
    "            fprintf(stderr, \\\"Failed to open tour diagnostics file: %s\\\\n\\\", tours_path);\\n"
    "            fclose(main_fp);\\n"
    "            tour_buffer_destroy(&buffer);",
    "        if (!tours_fp) {\\n"
    "            fprintf(stderr, \\\"Failed to open tour diagnostics file: %s\\\\n\\\", tours_path);\\n"
    "            if (convergence_fp) fclose(convergence_fp);\\n"
    "            fclose(main_fp);\\n"
    "            tour_buffer_destroy(&buffer);",
)
'''
if old not in text:
    raise SystemExit("Target block not found; script may already be repaired")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Repaired guarded replacement target")

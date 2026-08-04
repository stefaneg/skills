# Working in this repo

Read `CONTEXT.md` first — it defines source, tier, target, owned link, rescued skill.

## Rules

- **`skills.json` is the interface.** Adding or removing a skill means editing the
  manifest and running `bin/skills sync`. Never install a skill into a target by hand,
  and never edit an installed copy — sync overwrites it.
- **Install by copy, never symlink.** Sessions run sandboxed and cannot follow symlinks
  out of the sandbox. If you find yourself reaching for `ln -s`, stop.
- **Never edit `vendor/`.** It is a cache, wiped and rebuilt at will. To modify an
  external skill, copy it into `skills/`, change its entry to `source: "own"`, and note
  in the manifest why.
- **Default new skills to `tier: "on-demand"`.** Promoting to `auto` is a deliberate
  decision that costs attention from every other `auto` skill. Justify it.
- **Don't write to `~/.claude/settings.json`** unless the user asked for
  `--write-settings`. Show them `bin/skills overrides` output instead.
- `skills.lock.json` is generated. Don't hand-edit it; run `bin/skills update`.

## Authoring a skill in `skills/`

One directory per skill, `SKILL.md` at its root, `name` matching the directory name.
Keep the `description` narrow and trigger-shaped — it is the only thing the model sees,
and a vague description is worse than no skill, because it steals invocations from
skills that would have done the job.

Bundled assets (templates, scripts, reference docs) live inside the skill directory and
are referenced by relative path from `SKILL.md`.

## Testing a change to `bin/skills`

Don't test against the live targets. Copy the repo to a temp dir, rewrite `.targets` to
point inside it, and sync there:

```bash
T=$(mktemp -d); cp -R . "$T"/
jq '.targets = ["'"$T"'/out"]' "$T/skills.json" > "$T/s" && mv "$T/s" "$T/skills.json"
"$T/bin/skills" sync && ls -l "$T/out"
```

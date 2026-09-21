# Using FPF and its DPF Suites

Use the publications in this folder to help with the project's work. Paths below are relative to the folder containing this file.

When a referenced publication is present in this folder, resolve its pattern references in that copy, including references written as GitHub links. Use another edition when the task calls for an update or a comparison.

## Choose what to read

Start with the actual situation, the object being worked on, and the result the answer needs to support. If a pattern is already named, find it directly. Otherwise use `Readme.md` to choose a Suite or independent DPF. Each Suite folder has a `README.md` for first use and a named Reference for connecting contributions: `Foundational Thinking DPF Suite/FOUNDATIONAL-THINKING-DPF-SUITE-REFERENCE.md` or `Engineering DPF Suite/ENGINEERING-DPF-SUITE-REFERENCE.md`. Search for alternative formulations of the question; include English terms when the user's language differs from the sources.

To perform a selected method, read its description, applicability conditions, and the related patterns needed for that use. To use a particular technique, read its section together with the conditions it depends on. Apply it to the facts and constraints of the task.

Explain results and give feedback in the language of the project's work. Preserve the source distinctions that affect the answer. Cite the patterns and locations used. State assumptions, missing evidence, use limits, and the need for human judgement where they affect the decision. Let the current question determine the next step.

When a question needs several methods, use a relevant connected example or Practical-Use Card. Follow the intermediate results: what each method returns, which operation uses it, and what changed condition sends the work back. A mantra helps retain that connection. Read the supplying patterns and start at the contribution whose inputs are available.

Also recover the relevant Method vertical: what larger work is being performed through this action now, what constituent performances it needs, and which conditions must hold together. Use B.1.5.EW when this is unclear and B.1.5.RS for a proposed constituent replacement. A DPF can describe only part of the needed vertical. Retain already available capabilities, expose missing intermediate coordination or support, and check joint demands on shared resources. Use CGUS conditions when these facts change which continuation is available. Explain the connection in the language of the work; a formal stack diagram is optional.

## File structure

A publication contains several patterns, located by their IDs. For example:

| Markdown | Meaning |
| --- | --- |
| `## SYSE.24 - Choose How the Project Will Obtain a Needed Engineering Result` | Start of pattern `SYSE.24` |
| `### SYSE.24:4 - Solution` | Section of that pattern |
| `#### SYSE.24:4.1 - Name one result and one decision` | Subsection |
| `### SYSE.24:End` | End of the pattern |

IDs also occur in contents tables and cross-references. Match a heading at the start of a line to locate the pattern itself. Line numbers help retrieve portions of a file; IDs locate a pattern after its line numbers change. A reference such as `SYSE.24:4.1` points to a subsection; read it through to the next heading of the same or a higher level.

## Search and read

Use `rg` (ripgrep), or the environment's equivalent search tool with regular expressions. Run these commands with this folder as the working directory, or prepend its actual path to the file arguments.

Find Reference entries for “obtain a needed engineering result: build or buy”:

```sh
rg -n -i -C 2 'buy|build|obtain the result' -- "Engineering DPF Suite/ENGINEERING-DPF-SUITE-REFERENCE.md"
```

Locate the file and the start and end lines of the selected pattern:

```sh
rg -n --no-ignore -g '*.md' '^## SYSE\.24 |^### SYSE\.24:End[ \t]*\r?$' -- .
```

Read that pattern in full:

```sh
rg -U --no-heading --no-line-number --no-filename --color never '(?ms)^## SYSE\.24 [^\r\n]*\r?\n.*?^### SYSE\.24:End[ \t]*\r?$' -- "Engineering DPF Suite/SYSTEMS-ENGINEERING-PRINCIPLES-FRAMEWORK.md"
```

Here `-U` enables multiline search; `(?m)` makes `^` and `$` match line starts and ends, and `(?s)` lets a dot match a newline. `(?ms)` combines them. `.*?` matches through to the nearest specified `:End` heading; `\r?\n` accepts Windows and Unix line endings. Substitute another ID and file as needed; escape literal dots in IDs as `\.`.

For other searches, `-F` treats the query as literal text, `-i` ignores case, and `-C 2` includes neighbouring lines. `--no-ignore` searches files even in a Git-ignored folder; `-g '*.md'` selects Markdown files.

If the tool truncates a long result, read the selected text in successive line ranges with the available file reader. Folder search already covers separate publications; no combined file is needed.

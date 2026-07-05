# Record with: vhs demo.tape (produces demo.gif)
# Run from the repo root with the example requirements installed.

Output demo.gif

Set FontSize 15
Set Width 1200
Set Height 650
Set TypingSpeed 15ms

Type "export AUDIT_CHAIN_KEY=demo-key"
Enter
Sleep 300ms

Type "python examples/two-agent-app/app.py --runs 5 --seed 42 --audit"
Enter
Sleep 3s

Type "python skills/audit-log/scripts/verify_chain.py audit/run-000.jsonl"
Enter
Sleep 2500ms

Type "cp audit/run-000.jsonl /tmp/t.jsonl && cp audit/run-000.jsonl.head.json /tmp/t.jsonl.head.json"
Enter
Sleep 700ms

Type "python skills/audit-log/scripts/verify_chain.py /tmp/t.jsonl --demo-tamper"
Enter
Sleep 4s

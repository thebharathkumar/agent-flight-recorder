# Record with: vhs demo.tape (produces demo.gif)
# Run from the repo root with the example requirements installed.

Output demo.gif

Set FontSize 15
Set Width 1200
Set Height 650
Set TypingSpeed 40ms

Type "export AUDIT_CHAIN_KEY=demo-key"
Enter
Sleep 500ms

Type "python examples/two-agent-app/app.py --runs 5 --seed 42 --audit"
Enter
Sleep 4s

Type "python skills/audit-log/scripts/verify_chain.py audit/run-000.jsonl"
Enter
Sleep 3s

Type "cp audit/run-000.jsonl /tmp/tampered.jsonl && cp audit/run-000.jsonl.head.json /tmp/tampered.jsonl.head.json"
Enter
Sleep 1s

Type "python skills/audit-log/scripts/verify_chain.py /tmp/tampered.jsonl --demo-tamper"
Enter
Sleep 4s

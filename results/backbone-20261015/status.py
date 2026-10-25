import run
run.load_env()
import baselines
ssh = baselines.light_client()
try:
    code, out, err = baselines.exec_text(
        ssh,
        "ps -eo args | grep remote_one_trial.py | grep -v grep | sed 's|.*/baseline-jobs/||; s| .*||'",
        30,
    )
    print(out)
    print("err", err[-200:])
finally:
    ssh.close()

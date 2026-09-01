import pandas as pd

done = set(pd.read_csv(r"data\pop_master\pop_master_input.csv", dtype=str)["case_number"].astype(str))

email_log = pd.read_excel(
    r"data\input\AUG_2026\EMAIL_LOG\_POP_EmailsLog_2.xlsx",
    sheet_name="POP_attachments",
)

not_done = email_log[~email_log["Case Number"].astype(str).isin(done)]
print(f"Not yet processed: {len(not_done)}")
print(not_done[["Case Number"]].head(10).to_string(index=False))

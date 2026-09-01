from pathlib import Path

TEST_FOLDER = Path("testing_bank_statments")

for file in TEST_FOLDER.iterdir():
    print(file.name)
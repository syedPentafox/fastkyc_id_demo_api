import json
import pandas as pd


excel_file_path = r"C:\Users\Admin\Downloads\Bank.xlsx"  # Update path
df = pd.read_excel(excel_file_path)

# Rename columns to match model
df.rename(columns={
    'IFSC MAP': 'ifsc_code',
    'Bank/Fis': 'bank_name',
    'Bank Code': 'bank_code'
}, inplace=True)

# Fill missing IFSC codes and convert types
df.fillna({'ifsc_code': ''}, inplace=True)
df = df.astype({
    'bank_code': int,
    'bank_name': str,
    'ifsc_code': str
})

# Convert to list of dictionaries
bank_list = df.to_dict(orient='records')

# Save JSON for reference
json_file_path = 'bank_master.json'
with open(json_file_path, 'w', encoding='utf-8') as f:
    json.dump(bank_list, f, ensure_ascii=False, indent=4)

print("JSON file created successfully!")
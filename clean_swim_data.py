import pandas as pd

# Read the CSV file
df = pd.read_csv('YOTA 2024-2025 Time Data - Top Times(0).csv')

# Create a new Name column
df['Name'] = None

# Initialize variables
current_name = None

# Iterate through the rows
for idx, row in df.iterrows():
    # Check if this row only has a value in the first column
    if pd.isna(row['Event']) and pd.isna(row['Best Time']) and pd.isna(row['P/F/T']) and pd.isna(row['Date']) and pd.isna(row['Meet Name']):
        # This is a name row, update the current name
        current_name = row['Rank']
    else:
        # This is a data row, assign the current name
        df.at[idx, 'Name'] = current_name

# Remove rows that only contain the athlete name
df = df.dropna(subset=['Event'])

# Reorder columns to put Name first
cols = ['Name'] + [col for col in df.columns if col != 'Name']
df = df[cols]

# Save the cleaned data to a new CSV file
df.to_csv('cleaned_swim_data.csv', index=False)

print("Data cleaning complete! Saved to 'cleaned_swim_data.csv'") 
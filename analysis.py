import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# load CSV into pandas
CSV_PATH = "survey.csv"
df = pd.read_csv(CSV_PATH)

# store in an in-memory SQLite database for SQL queries
conn = sqlite3.connect(":memory:")
df.to_sql("survey", conn, index=False, if_exists="replace")

###### basic inspections

print(f"Shape (rows, columns): {df.shape}")

print("\n" + "-" * 100)
print("\nColumns:")
print(list(df.columns))

print("\n" + "-" * 100)
print("\nData Types:\n")
print(df.dtypes)

print("\n" + "-" * 100)
print("\nFirst 5 rows:\n")
print(df.head())

######################## data quality checks
# 1 - age range
print("\n" + "=" * 100)
print("DATA QUALITY CHECK\n")

print("1 - age range check\n")
query_age = """
SELECT MIN(Age) min_age, MAX(Age) max_age 
FROM survey
"""
print(pd.read_sql(query_age, conn))

# 2 - gender  
print("\n" + "-" * 100)
print("2 - gender check\n")
query_gender = """
SELECT Gender, COUNT(*) as count
FROM survey
GROUP BY Gender
ORDER BY count DESC
LIMIT 15;
"""
print(pd.read_sql(query_gender, conn))

# 3 - null/missing values count
print("\n" + "-" * 100)
print("3 - missing values count\n")
query_nulls = """
SELECT 
    COUNT(*) - COUNT(Age) AS missing_age,
    COUNT(*) - COUNT(Gender) missing_gender,
    COUNT(*) - COUNT(self_employed) missing_self_employed,
    COUNT(*) - COUNT(work_interfere) missing_work_interfere
FROM survey;
"""
print(pd.read_sql(query_nulls, conn))

# 4 - duplicate rows 
print("\n" + "-" * 100)
print("4 - duplicate row check\n")

query_dupes = """
SELECT Timestamp, Age, Gender, Country, COUNT(*) dupe_count
FROM survey
GROUP BY Timestamp, Age, Gender, Country
HAVING dupe_count > 1;
"""
print(pd.read_sql(query_dupes, conn))

########################### data cleaning

print("\n" + "=" * 100)
print("DATA CLEANING\n")

initial_rows = len(df)
print(f"Starting row count: {initial_rows}")

# 1 - filter ages (use working age threshold 18-100)
df_clean = df[(df["Age"] >= 18) & (df["Age"] <= 100)].copy() #boolean indexing and duplicate filtered data into a separate memory block
age_dropped = initial_rows - len(df_clean)
print(f"# of rows dropped due to invalid age (< 18 or > 100): {age_dropped}")
print(f"Row count after age filter: {len(df_clean)}")

# 2. Standardize Gender column
def clean_gender(val):
    if pd.isna(val): #pd.isna(...) detects if ... is a missing values eg python's None, NumPy's np.nan (Not a Number), or pandas pd.NA
        return "Other / Not Specified"
    g = str(val).strip().lower() #type cast into string; trim leading/trailing white spaces; convert to lowercases
    
    # Common male representations and typos
    male_terms = {"male", "m", "make", "cis male", "man", "cis man", "msle", "mail", "malr"}
    # Common female representations and typos
    female_terms = {"female", "f", "woman", "cis female", "femake", "female (cis)", "cis-female", "femme", "femail"}
    
    if g in male_terms:
        return "Male"
    elif g in female_terms:
        return "Female"
    else:
        return "Other / Not Specified"

df_clean["Gender_Cleaned"] = df_clean["Gender"].apply(clean_gender) #do not use clean_gender() -> called once immediately rather than row by row

print("\nCleaned Gender value counts:")
print(df_clean["Gender_Cleaned"].value_counts()) #equiv to SELECT col, COUNT(*) ... GROUP BY col ORDER BY count DESC

# 3 - handle missing values in fields
df_clean["self_employed"] = df_clean["self_employed"].fillna("Not Specified")
df_clean["work_interfere"] = df_clean["work_interfere"].fillna("Not Specified")

print(f"\nRemaining missing values in self_employed: {df_clean['self_employed'].isna().sum()}") #boolean sum
print(f"Remaining missing values in work_interfere: {df_clean['work_interfere'].isna().sum()}")

print(f"\nFinal cleaned row count: {len(df_clean)}")

#################### Q1: "Do respondents whose employers offer mental health benefits report seeking treatment more often?"
#################### Q2: "Do respondents with a family history of mental illness report seeking treatment more often?"
print("\n" + "=" * 100)
print("Q: TREATMENT RATES BY WORKPLACE BENEFITS & FAMILY HISTORY")

# 1 - Workplace Benefits vs Treatment Rate
benefits_summary = (
    df_clean.groupby("benefits")
    .agg(
        total_count=("treatment", "count"),
        treatment_yes=("treatment", lambda x: (x == "Yes").sum()),
        treatment_rate_pct=("treatment", lambda x: (x == "Yes").mean() * 100),
    )
    .reset_index() 
    #convert "benefits" column back to standard column and reset row index to 0,1,.. instead of "benefits"
)

print("\n--- Treatment Rate by Workplace Benefits ---\n")
print(benefits_summary.round(2))
print("\n\n")

# Breakdown 2: Family History vs Treatment Rate
family_summary = (
    df_clean.groupby("family_history")
    .agg(
        total_count=("treatment", "count"),
        treatment_yes=("treatment", lambda x: (x == "Yes").sum()),
        treatment_rate_pct=("treatment", lambda x: (x == "Yes").mean() * 100),
    )
    .reset_index()
)

print("\n--- Treatment Rate by Family History of Mental Illness ---\n")
print(family_summary.round(2))
print("\n\n")

############################### Charts 

print("\n" + "=" * 100)
print("CHARTS")

# --- Chart 1: Benefits vs Treatment Rate ---
fig, ax = plt.subplots(figsize=(7, 5))

# x-labels that include sample sizes N; bars 
# iterrows iterates through data frames one by one 
x_labels_benefits = [
    f"{row['benefits']}\n(N={row['total_count']})" 
    for _, row in benefits_summary.iterrows()
]
bars1 = ax.bar(x_labels_benefits, benefits_summary["treatment_rate_pct"], color="#4795EF", width=0.55)
#create bars by passing x labels, heights (y value),...

ax.set_title("Treatment-Seeking Rate by Employer Mental Health Benefits", fontsize=12, pad=15)
ax.set_ylabel("Reported Seeking Treatment (%)", fontsize=10)
ax.set_ylim(0, 85)

# data labels for each bar
for bar in bars1:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, height + 1.5, f"{height:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
#ha/va : horizontal/vertical alignment

plt.tight_layout()
plt.savefig("treatment_by_benefits.png", dpi=300)
plt.close()
print("Saved: treatment_by_benefits.png")

# --- Chart 2: Family History vs Treatment Rate ---
fig, ax = plt.subplots(figsize=(6, 5)) #plt.subplots(...) returns (figure, axes) tuple, assigns to fig, ax

x_labels_family = [
    f"Family History: {row['family_history']}\n(N={row['total_count']})" 
    for _, row in family_summary.iterrows()
]
bars2 = ax.bar(x_labels_family, family_summary["treatment_rate_pct"], color="#50E3C2", width=0.45)

ax.set_title("Treatment-Seeking Rate by Family History", fontsize=12, pad=15)
ax.set_ylabel("Reported Seeking Treatment (%)", fontsize=10)
ax.set_ylim(0, 95)

# data labels for each bar
for bar in bars2:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, height + 1.5, f"{height:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

plt.tight_layout()
plt.savefig("treatment_by_family_history.png", dpi=300)
plt.close()
print("Saved: treatment_by_family_history.png")

# close the database connection 
conn.close()
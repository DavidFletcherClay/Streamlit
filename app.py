import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("David and his first app. Nerd!!! But he tries")

# Load the Excel file
df = pd.read_excel('testing.xlsx')


# Dropdown to select column
column = st.selectbox("Select:", ['Act', 'Bud', 'PY', 'PPY'])

# Plot the selected column
st.subheader(f"Line Chart shown below - {column}")
fig, ax = plt.subplots()
ax.plot(df['Month'], df[column])
ax.set_xlabel("Month")
ax.set_ylabel(column)
plt.xticks(rotation=45)

st.pyplot(fig)

st.subheader("Raw Data")
st.dataframe(df)

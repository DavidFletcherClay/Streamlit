import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("David and his first app. Nerd!!!")

# Load the Excel file
df = pd.read_excel('testing.xlsx')

# Show the dataframe
#st.subheader("Raw Data")
#st.dataframe(df)

# Dropdown to select column
column = st.selectbox("Select:", ['Act', 'Bud', 'PY'])

# Plot the selected column
st.subheader(f"Line Chart - {column}")
fig, ax = plt.subplots()
ax.plot(df['Month'], df[column])
ax.set_xlabel("Month")
ax.set_ylabel(column)
plt.xticks(rotation=45)

st.pyplot(fig)
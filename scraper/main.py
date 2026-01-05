from dbsetup import table_create
from html_storer import store_html

# #####
# target = "https://www.congress.gov/bill/119th-congress/senate-bill/232/text"
#
# result = store_html(target)
# if result:
#     print(f"HTML stored successfully with ID: {result}")
# else:
#     print("Failed to store HTML")
#
from selenium import webdriver

driver = webdriver.Firefox()

driver.get("https://www.google.com")
print("Driver installed and running automatically!")
driver.quit()



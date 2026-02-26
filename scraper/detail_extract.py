
def congress_extract(url):
    parts = url.strip("/").split("/") # splits url into parts 
    bill_idx = parts.index("bill")
    congress_number_extract = parts[bill_idx + 1] #always one after bill 
    bill_type_extract = parts[bill_idx + 2] # two after bill
    bill_number = parts[bill_idx + 3] # three after bill 

    congress_num = int(''.join(filter(str.isdigit, congress_number_extract)))
    # now find bill type 
    bill_type = ""
    if(bill_type_extract == "senate-bill"):
        bill_type = "s"
    elif(bill_type_extract == "senate-resolution"):
        bill_type = "sres"
    elif(bill_type_extract == "senate-joint-resolution"):
        bill_type = "sjres"
    elif (bill_type_extract == "senate-concurrent-resolution"):
        bill_type = "sconres"
    elif(bill_type_extract == "house-bill"):
        bill_type = "hr"
    elif(bill_type_extract == "house-resolution"):
        bill_type = "hres"
    elif(bill_type_extract == "house-joint-resolution"):
        bill_type = "hjres"
    elif (bill_type_extract == "house-concurrent-resolution"):
        bill_type = "hconres"
    else:
        bill_type = "unknown"
    return congress_num, bill_type, bill_number

if __name__ == "__main__":
    url = "https://www.congress.gov/bill/101st-congress/senate-bill/933/text"
    congress_num, bill_type, bill_number = congress_extract(url)
    print(congress_num, bill_type, bill_number)
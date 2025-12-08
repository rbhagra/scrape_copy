Scraper to pull definitions regarding AI policy terms from federal legislation 
1. prompts user for HTML/XML link of federal legislation
2. searches for identifies definitions header in xml
3. identifies section in xml
4. indentifies paragraphs within sections
5. loops through paragraphs tags to each individual paragraph (federal bill definitions are written in seperate paragraphs)
6. Strips term from paragraph texts, uses dictionary to save term & definition concurrently

-- built in fallbacks if no definitions header through node searching. Fallbacks also for subsequent parts. 

NOTE: Will not work without explicitly labeled definitions section. Currently XML only, (with all federal legislation available in XML format)

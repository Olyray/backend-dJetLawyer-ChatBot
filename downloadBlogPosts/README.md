# How to use
1. Add the required urls to the `urls.json` file.
2. In main.py, change the pdf_directory variable to the location of the new sub directory where you want to store the pdfs. 
3. Run main.py. This would download the pdf version of the blog posts and map them to the downloaded_pdfs.json file. 
4. The downloaded_pdfs.json file is used in the vector store to ultimately map an entry to a source. 
5. Change the `document_path` variable in `../createVectorDatabase.py` to the new directory where you downloaded the PDFs to. 
6. Also modify the search key in `url = pdf_urls.get(f"./blog_pdfs/{filename}", "Unknown URL")` in `../createVectorDatabase.py` to the directory of the file you want to search for. For instance, changing it from `blog_pdfs` to `blog_pdfs/dJetLawyer_LFN`.
7. Run createVectorDatabase.py to populate the vector database.


## For files that are not from the website
For files that aren't gotten from the website, add the file manually to the target directory. Then add the file and its mapping to the `downloaded_pdfs.json` file.
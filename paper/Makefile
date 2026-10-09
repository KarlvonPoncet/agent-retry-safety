.PHONY: all pdf clean

all: paper.html

pdf:
	../.venv/bin/python ../scripts/build_paper_pdf.py

paper.html: paper.md ../scripts/build_paper.py
	python3 ../scripts/build_paper.py

clean:
	rm -f paper.html

.PHONY: all clean

all: paper.html

paper.html: paper.md ../scripts/build_paper.py
	python3 ../scripts/build_paper.py

clean:
	rm -f paper.html

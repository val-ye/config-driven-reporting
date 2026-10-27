.PHONY: all data model report test figures clean
all: data model report
data:   ; python generator/make_synthetic.py
model:  ; python model/build.py
report: ; python report/render.py
test:   ; python tests/test_resolve.py
figures: ; python figures/make_figures.py
clean:  ; rm -rf data/*.csv data/*.duckdb reports

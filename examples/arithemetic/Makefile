CFLAGS = -O0 -g -Wno-unused-function
#you can uncomment this to make it define DBG in the c file
#CPLGEN_FLAGS = -v
CPLGEN_FLAGS = 

.phony: all clean
all: arith

parse.sp.c: arith.gram 
	../../src/generate_slr_c.py --in $< $(CPLGEN_FLAGS) > $@ 
arith: parse.sp.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LDLIBS)
clean:
	rm -f arith parse.sp.c

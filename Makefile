CC = gcc
CFLAGS = -Wall -Wextra -O2 -Iinclude

TARGET = build/main
SRC = src/main.c src/lattice.c src/percolation.c src/cluster.c src/io.c src/config.c src/simulation.c src/simulation_runner.c src/simulation_p_incremental.c src/union_find.c src/coordinate_hash_set.c src/random_walk.c src/simulation_random_walk.c src/perm.c

all: $(TARGET)

$(TARGET): $(SRC)
	mkdir -p build
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET) -lm
	
run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
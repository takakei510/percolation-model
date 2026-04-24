CC = gcc
CFLAGS = -Wall -Wextra -O2 -Iinclude

TARGET = build/main
SRC = src/main.c src/lattice.c src/percolation.c src/cluster.c src/io.c src/config.c src/simulation.c

all: $(TARGET)

$(TARGET): $(SRC)
	mkdir -p build
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET) -lm
	
run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
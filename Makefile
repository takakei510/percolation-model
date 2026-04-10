CC = gcc
CFLAGS = -Wall -Wextra -O2 -Iinclude

TARGET = build/main
SRC = src/main.c src/lattice.c src/percolation.c src/cluster.c src/io.c src/config.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
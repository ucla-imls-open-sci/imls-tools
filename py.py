import sys

def on_exit():
    # Add your code to run when Ctrl+C is pressed here
    print("Ctrl+C was pressed. Exiting gracefully.")
    sys.exit(0)

try:
    # Your main program logic here
    while True:
        pass  # Replace this with your actual program code
except KeyboardInterrupt:
    on_exit()

# VHS Tape: A.R.E.S. CLI Showcase
# Run: vhs assets/demo.tape (requires vhs from https://github.com/charmbracelet/vhs)

Output assets/ares-demo.gif
Output assets/ares-demo.mp4

Set FontSize 15
Set FontFamily "JetBrains Mono"
Set Width 1280
Set Height 720
Set LetterSpacing 0
Set LineHeight 1.2
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 30

# Initial screen
Type "ares-cli --target scanme.nmap.org"
Sleep 600ms
Enter

# Wait for banner and initial prompt
Sleep 2.5s

# Type audit objective
Type "Audit target for web vulnerabilities and open security ports"
Sleep 800ms
Enter

# Observe AI planning, tool checks, and command generation
Sleep 4s

# Approve initial step
Type "y"
Sleep 500ms
Enter

# Let execution and markdown reporting render
Sleep 6s

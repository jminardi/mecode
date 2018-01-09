from main import G
layer_height = 0.3
with G(outfile='mixed_spiral_singlelayer.pgm',aerotech_include=True,print_lines=False) as g:
	# Turn on Velocity Profiling Mode
	g.write("VELOCITY ON")
	# Turn on spindle at 5rps
	g.write("FREERUN c 5")
	# Use the A axis for z
	g.rename_axis(z='A')
	# Move to printing height
	g.abs_move(z=layer_height)
	# Print gradient spiral
	g.gradient_spiral(start_diameter=7.62, #mm
		end_diameter=30.48, #mm
		spacing=1, #mm
		feedrate=8, #mm/s
		flowrate=2/60.0, #rot/s
		start='edge', #'edge' or 'center'
		direction='CW', #'CW' or 'CCW'
		gradient="-0.322*r**2 - 6.976*r + 131.892") #Any function
		#gradient="3*(r-9.525)**2")
	# Move away from layer
	g.move(z=10)
	# Turn off spindle
	g.write("FREERUN c 0")
	# Turn off Velcoity Profiling Mode
	g.write("VELOCITY OFF")
	g.view(backend='matplotlib2d')
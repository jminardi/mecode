from main import G
layer_height = 0.4
with G(outfile='mixing_print_files/mixed_spiral_multilayer_wDead.pgm',aerotech_include=False,print_lines=False) as g:
	g.write("VELOCITY ON")
	# Use the A axis for z
	g.rename_axis(z='A')
	# Turn on spindle at 5rps
	g.write("FREERUN c 5")
	# Move to printing location to start purge meander
	g.abs_move(x=-30.48,y=30.48+15,z=layer_height)
	# Print purge meander
	g.feed(8)
	g.purge_meander(x=30.48,y=10.0,spacing=1,start='UL',volume_fraction=0)
	# Turn the spindle off to prevent ozzing
	g.write("FREERUN c 0")
	# Disable and re-eneable motors to avoid error
	g.write('DISABLE a b')
	g.write('ENABLE a b')
	# Move away from the meander at higher feedrate
	g.feed(40)
	# Print gradient spiral
	layer_order = ['edge','center','edge','center','edge','center','edge']
	direction_order = ['CW','CCW','CW','CCW','CW','CCW','CW']
	# Set first layer height to regular layer height
	height = layer_height
	#Turn on the spindle
	g.write("FREERUN c 5")
	for layer, direction in zip(layer_order,direction_order):
		# Print gradient spiral layer
		g.gradient_spiral(start_diameter=2*7.62, #mm
			end_diameter=2*30.48, #mm
			spacing=1, #mm
			feedrate=8, #mm/s
			flowrate=2/60.0, #rot/s
			start=layer, #'edge' or 'center'
			direction=direction, #'CW' or 'CCW'
			center_position = [0,0], #Location of spiral center (required for >1 layer)
			gradient="0.7437*exp(0.1482*r)", #Dielectric as a function of the radius
			dead_delay = 0.0) #mm 125mm for last attempt
		# Disable and re-eneable motors to avoid error
		g.write('DISABLE a b')
		g.write('ENABLE a b')
		#Move up to next layer at higher speed
		height += layer_height
		g.feed(40)
		g.abs_move(z=height)
	# Turn off spindle
	g.write("FREERUN c 0")
	# Move away from layer
	g.feed(40)
	g.move(z=10)
	g.move(x=80)
	# Turn off Velcoity Profiling Mode
	g.write("VELOCITY OFF")
	# Visualize gcode
	#g.view(backend='matplotlib',outfile='image.png')
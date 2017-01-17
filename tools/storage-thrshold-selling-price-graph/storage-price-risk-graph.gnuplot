# Gnuplot script to Plot the dependency of selling threshold price and Risk 
set terminal png
set output 'storage_threshold_price.png'
set title "Graph illustrating the threshold prics for energy selling"
set xlabel "Risk"
set ylabe "Price in percentage"
set xrange [0.0:100.0]
set yrange [90:125.0]

f(x) = 101 * (1 + ((x/100) * 0.2))
plot f(x)

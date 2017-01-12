set datafile separator ','
set terminal png
set output 'values.png'
set title "Fit real measured PV data to gaussian-function" 
set xlabel "Time in 5 minute slots" 
set ylabel "Produced Energy in Wh" 
set xrange [-1:280]
set yrange [-1:180]
a = 100
b = 146
g = 10

simplelorentz(x) = (a*g)/((g*((x-b)**2))+g**3) 
fit simplelorentz(x) 'real-production-data.csv' using 0:1 via a, b, g
plot 'real-production-data.csv' using 0:1, simplelorentz(x)

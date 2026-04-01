% Load CSV data

clc; clear; close all;

data = readtable('finaltest.csv', 'VariableNamingRule', 'preserve');

% Set filter parameters
phiToPlot = 0;       % degrees
freqToPlot = linspace(2, 18 ,17);   % GHz
tol = 1e-3;          


for i = 1:length(freqToPlot)

freq = freqToPlot(i);

% Filter for phi = 0 and desired frequency
idx = abs(data.('Theta (deg)') - phiToPlot) < tol & ...
  abs(data.('Frequency (GHz)') - freq) < tol;

theta = data.('Phi (deg)')(idx);
mag_dB = data.('Magnitude (dB)')(idx);

% Sort by theta for a clean line plot
[theta_sorted, sortIdx] = sort(theta);
mag_sorted = mag_dB(sortIdx);

% Plot
figure;
plot(theta_sorted, mag_sorted, 'b-', 'LineWidth', 2);
xlabel('Theta (deg)');
ylabel('Magnitude (dB)');
title(sprintf('Rectangular Plot at \\phi = %.0f°, f = %.2f GHz', phiToPlot, freq));
grid on;
end

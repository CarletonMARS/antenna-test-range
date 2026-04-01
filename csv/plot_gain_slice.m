% Clear workspace
clc; clear all; close all;

% Load CSVs for two polarizations
data1 = readtable('test5.csv', 'VariableNamingRule', 'preserve');

% Frequency to plot
freqToPlot = 8; % GHz
freqTolerance = 0.001;

% Filter at desired frequency
idx1 = abs(data1.('Frequency (GHz)') - freqToPlot) < freqTolerance;

theta_deg1 = data1.('Theta (deg)')(idx1);
phi_deg1   = data1.('Phi (deg)')(idx1);
mag1_db    = data1.('Magnitude (dB)')(idx1);

%% Choose slice orientation
slice_mode = 'theta';  % 'theta' or 'phi'
angle_val = 0;        % θ or φ value to slice at

if strcmpi(slice_mode, 'theta')
    row_idx = theta_deg1 == angle_val;
    x_angle = phi_deg1(row_idx);
    gain = mag1_db
    xlabel_text = '\phi (deg)';
elseif strcmpi(slice_mode, 'phi')
    row_idx = phi_deg1 == angle_val;
    x_angle = theta_deg1(row_idx);
    gain = mag1_db
    xlabel_text = '\theta (deg)';
else
    error('Invalid slice mode. Use ''theta'' or ''phi''.');
end

% Sort for plotting
[x_angle_sorted, sort_idx] = sort(x_angle);
gain_sorted = gain(sort_idx);

%% Plot
figure;
plot(x_angle_sorted, gain_sorted, 'LineWidth', 2);
grid on;
xlabel(xlabel_text);
ylabel('Normalized Total Gain (dB)');
title(sprintf('Gain Slice at %s = %d°', upper(slice_mode), angle_val));
xlim([min(x_angle_sorted), max(x_angle_sorted)]);
set(gcf, 'Color', 'w');

% Display table
T = table(x_angle_sorted, gain_sorted, 'VariableNames', {xlabel_text, 'NormalizedGain_dB'});
disp(T);

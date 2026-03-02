% Clear workspace and command window
clc; clear all; close all;

% Load CSVs for two polarizations
data1 = readtable('testfixed.csv', 'VariableNamingRule', 'preserve');  % First polarization
data2 = readtable('testfixed2.csv', 'VariableNamingRule', 'preserve');  % Second polarization
data3 = readtable('lash.csv','VariableNamingRule', 'preserve');  

% Pick frequency to plot
freqToPlot = 2; % GHz
freqTolerance = 0.001;

% Filter both datasets at that frequency
idx1 = abs(data1.('Frequency (GHz)') - freqToPlot) < freqTolerance;
idx2 = abs(data2.('Frequency (GHz)') - freqToPlot) < freqTolerance;
idx3 = abs(data3.('Frequency (GHz)') - freqToPlot) < freqTolerance;
% Extract angle and magnitude info
theta_deg1 = data1.('Theta (deg)')(idx1);
phi_deg1   = data1.('Phi (deg)')(idx1);
mag1_db    = data1.('Magnitude (dB)')(idx1);

theta_deg2 = data2.('Theta (deg)')(idx2);
phi_deg2   = data2.('Phi (deg)')(idx2);
mag2_db    = data2.('Magnitude (dB)')(idx2);

theta_deg3 = data3.('Theta (deg)')(idx3);
phi_deg3   = data3.('Phi (deg)')(idx3);
mag3_db    = data3.('Magnitude (dB)')(idx3);


% Check that the angle data matches between the two
if ~isequal(theta_deg1, theta_deg2) || ~isequal(phi_deg1, phi_deg2)
    error('Angle grids do not match between the two datasets.');
end


% Convert dB to linear magnitude (field, not power)
mag1_lin = 10.^(mag1_db / 20);
mag2_lin = 10.^(mag2_db / 20);

% Vectorial sum (assuming same phase; otherwise need phase info)
mag_total_lin = sqrt(mag1_lin.^2 + mag2_lin.^2);  % total E = sqrt(Ex^2 + Ey^2)

% Convert back to dB
mag_total_db = 20 * log10(mag_total_lin);


% Normalize so that max is 0 dB
mag_total_db_norm = mag_total_db - max(mag_total_db);
disp(max(mag_total_db));
%% Plot
patternCustom(mag3_db, theta_deg3, phi_deg3);
patternCustom(mag3_db, theta_deg3, phi_deg3);
colormap(jet);

% Formatting
cb = colorbar;
ylabel(cb, 'Normalized Total Gain (dB)');

set(groot, 'DefaultAxesFontName', 'Times');
set(groot, 'DefaultTextFontName', 'Times');
set(groot, 'DefaultAxesFontSize', 14);
set(groot, 'DefaultTextFontSize', 14);

% Choose theta value to inspect
theta_to_check = 0; % degrees

% Find all matching entries
row_idx = theta_deg1 == theta_to_check;

% Extract phi and normalized total gain
phi_row = phi_deg1(row_idx);
gain_row = mag_total_db_norm(row_idx);

% Combine into table
T = table(phi_row, gain_row, 'VariableNames', {'Phi_deg', 'NormalizedGain_dB'});

% Sort by Phi
T = sortrows(T, 'Phi_deg');

% Display
disp(T);



clc; clear; close all;

%% USER INPUT
folder = "2025-12-13"; 
input_file_name = "Measured Data/Co-Pol - E-Plane.csv";        % CSV or Excel file
output_file_name = "Peak S21 vs Frequency.csv";
freq_new = 2:0.1:18;              % frequencies you want to interpolate

%% READ DATA
data = readmatrix(fullfile(folder, input_file_name), NumHeaderLines=6);        % adjust NumHeaderLines if needed

phi = data(:,1);
theta = data(:,2);
freq = data(:,3);
S21_dB = data(:,4);

%% FIND PEAK S21 FOR EACH ORIGINAL FREQUENCY
unique_freq = unique(freq);
peak_S21_dB = zeros(size(unique_freq));

for k = 1:length(unique_freq)
    f = unique_freq(k);
    idx = freq == f;
    peak_S21_dB(k) = max(S21_dB(idx));
end

%% INTERPOLATE PEAK S21 OVER NEW FREQUENCY GRID
% Convert to linear
peak_S21_lin = 10.^(peak_S21_dB./20);       % voltage/magnitude scale
peak_S21_lin_new = interp1(unique_freq, peak_S21_lin, freq_new, 'linear', 'extrap');

% Back to dB
peak_S21_dB_new = round(20*log10(peak_S21_lin_new), 2);

%% PLOT SANITY CHECK
figure;
plot(unique_freq, peak_S21_dB, 'o', 'DisplayName', 'Original Peaks');
hold on;
plot(freq_new, peak_S21_dB_new, '-', 'LineWidth', 2, 'DisplayName', 'Interpolated');
grid on; grid minor;
xlabel('Frequency (GHz)'); ylabel('Peak S21 (dB)');
title('Peak S21 Interpolation');
legend('Box','off');

%% EXPORT TO CSV
headers = {'Frequency (GHz)','Peak S21 (dB)'};
output_data = [freq_new(:), peak_S21_dB_new(:)];
output_cell = [headers; num2cell(output_data)];
writecell(output_cell, fullfile(folder, output_file_name));

disp("Saved interpolated peak S21 to: " + fullfile(folder, output_file_name));

clc; clear; close all;

%% USER INPUT

filename = "Archive/Gain vs Freq (WebDigitizer).csv"; 
data = readmatrix(filename); 

% Original data which we want to interpolate from 
freq = data(:, 1);          
gain_dB = data(:, 2);      

% We want to interpolate over 2 to 18 GHz in 0.25 GHz steps
freq_new = 2:0.1:18; 


%% INTERPOLATION
%  Convert to linear scale, interpolate, then convert back to dB

gain_linear = 10.^(gain_dB/10);                         % dB → linear
gain_linear_new = interp1(freq, gain_linear, freq_new); % interpolate
gain_new_dB = round(10*log10(gain_linear_new), 2);                % linear → dB

%% PLOT FOR SANITY CHECK

figure;
plot(freq, gain_dB, LineWidth=2.5, DisplayName='WebDigitizer'); 
hold on;
plot(freq_new, gain_new_dB, LineWidth=2.5, DisplayName='Interpolated');
grid on;
grid minor; 
xlabel("Frequency");
ylabel('Gain (dB)');
title('Interpolated Gain vs Frequency');
legend(Box='off', Location='best');

ax = gca;
ax.LineWidth = 1.2;
ax.XMinorTick = "on";
ax.YMinorTick = "on";
ax.TickLength = [0.02, 0];
ax.Box = "on";


%% WRITE TO EXCEL FILE

output_filename = "Standard Horn - Gain vs Frequency.csv"; 
headers = {"Frequency (GHz)", "Gain (dB)"}; 
output_data = [freq_new(:), gain_new_dB(:)]; 
output_cell = [headers; num2cell(output_data)]; 

writecell(output_cell, output_filename); 

disp("Saved interpolated data with headers to: " + output_filename);
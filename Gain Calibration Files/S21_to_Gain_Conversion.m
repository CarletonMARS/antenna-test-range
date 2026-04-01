% =========================================================================
% Script which converts raw S21 values from a VNA to gain
%
% Description:
%   This script processes raw radiation pattern measurement data exported
%   from the measurement system and generates calibrated gain datasets.
%   The processing pipeline includes:
%
%     1) Conversion of measured S21 (dB) to calibrated gain (dB) using
%        standard horn calibration data.
%     2) Automatic identification of vertical and horizontal cut datasets
%        (Vcut / Hcut) based on filename keywords, followed by
%        appropriate angular rotations.
%     3) Wrapping of angular coordinates to the range [-180°, 180°].
%     4) Sorting of angular data (phi/theta) independently at each
%        frequency point to ensure consistent ordering.
%     5) Export of processed data to CSV format with standardized headers.
%
% Inputs:
%   - CSV files containing raw radiation pattern data
%   - Standard horn calibration file (frequency vs. gain offset)
%
% Outputs:
%   - CSV files containing:
%         [Phi (deg), Theta (deg), Frequency (GHz),
%          Calibrated Gain (dB), S21 (dB)]
%
% User Configuration:
%   - Input/output directories
%   - File filtering string (e.g., contains_str = "Co-Pol", "Cross-Pol")
%   - Column indices for raw data
%
% Notes:
%   - The script assumes a fixed header length (6 lines) in input files.
%   - The last row ("End of Test") is automatically removed.
%   - Linear interpolation is used for calibration offsets.
%
% Author: David F. Hardy
% Date: 2026-APRIL-01
% =========================================================================

clc; clear; close all;

% =========================================================================
% Load Data and Setup Output
% =========================================================================

input_folder  = "Sample Files/Raw";
output_folder = "Sample Files/Calibrated";
file_ext      = ".csv";

% Modify this string if you only want to apply the processing to certain
% ... files in the input folder 
contains_str  = ""; 

phi_col    = 1;
theta_col  = 2;
freq_col   = 3;
S21_dB_col = 4;

Vcut_angle_offset = 0; 
Hcut_angle_offset = 0; 

% =========================================================================
% Load Horn Antenna Calibration File
% =========================================================================

std_horn_data = readmatrix("2025-12-13 - Gain Calibration.csv");
std_freq      = std_horn_data(:, 1);
std_offset_dB = std_horn_data(:, 4);  % offset column

% =========================================================================
% Locate Raw Files
% =========================================================================

% Get all CSV files first
files = dir(fullfile(input_folder, "*" + file_ext));

% Apply optional filtering based on contains_str
if strlength(strtrim(contains_str)) > 0
    mask = contains({files.name}, contains_str, "IgnoreCase", true);
    files = files(mask);
end

% Error if nothing found
if isempty(files)
    if strlength(strtrim(contains_str)) > 0
        error("No files containing '%s' found in %s", contains_str, input_folder);
    else
        error("No CSV files found in %s", input_folder);
    end
end

% =========================================================================
% Process Each File
% =========================================================================

for n = 1:length(files)

    raw_file = erase(files(n).name, file_ext);
    raw_path = fullfile(input_folder, files(n).name);

    fprintf("Processing: %s\n", files(n).name);

    % Load Raw Data
    raw_data = readmatrix(raw_path, NumHeaderLines=6);

    % Remove last row ("End of Test")
    raw_data(end,:) = [];

    phi    = raw_data(:, phi_col);
    theta  = raw_data(:, theta_col);
    freq   = raw_data(:, freq_col);
    S21_dB = raw_data(:, S21_dB_col);

    % Apply Angle Corrections
    is_H_cut = contains(files(n).name, "Hcut", "IgnoreCase", true);
    is_V_cut = contains(files(n).name, "Vcut", "IgnoreCase", true);

    % Validate cut type from filename
    if ~is_H_cut && ~is_V_cut
        error("File '%s' does not specify cut type (Hcut or Vcut) in its name.", files(n).name);
    end

    if is_H_cut
        phi = wrapTo180(phi - Hcut_angle_offset);
    end

    if is_V_cut
        theta = wrapTo180(theta - Vcut_angle_offset);
    end

    % Compute Gain

    unique_freq = unique(freq);
    gain_dB = zeros(size(S21_dB));

    for k = 1:length(unique_freq)

        f = unique_freq(k);
        idx = (freq == f);

        offset_dB = interp1(std_freq, std_offset_dB, f, ...
                            'linear', 'extrap');

        gain_dB(idx) = S21_dB(idx) + offset_dB;
    end

    % Sort angles (from descending to ascending) 

    phi_s    = phi;
    theta_s  = theta;
    freq_s   = freq;
    gain_s   = gain_dB;
    S21_s    = S21_dB;

    for k = 1:length(unique_freq)

        f = unique_freq(k);
        idx = find(freq == f);

        if is_V_cut
            [~, sidx] = sort(theta(idx));
        else
            [~, sidx] = sort(phi(idx));
        end

        phi_s(idx)    = phi(idx(sidx));
        theta_s(idx)  = theta(idx(sidx));
        freq_s(idx)   = freq(idx(sidx));
        gain_s(idx)   = gain_dB(idx(sidx));
        S21_s(idx)    = S21_dB(idx(sidx));
    end

    % Write calibrated data to a CSV 

    output_file = raw_file + ".csv";
    output_path = fullfile(output_folder, output_file);

    headers = {"Phi (deg)", "Theta (deg)", "Freq (GHz)", ...
               "Gain (dB)", "S21 (dB)"};

    output_data = [phi_s(:), theta_s(:), freq_s(:), ...
                   gain_s(:), S21_s(:)];

    output_cell = [headers; num2cell(output_data)];

    writecell(output_cell, output_path);

    fprintf("  → Saved to: %s\n", output_path);

end

disp("All Co-Pol files processed successfully.");

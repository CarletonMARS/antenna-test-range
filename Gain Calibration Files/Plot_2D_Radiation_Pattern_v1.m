clc; clear all; close all;

files_dir = "Sample Files/Calibrated"; 
file_ext = ".csv"; 

% =========================================================================
% Choose files to process
% =========================================================================
% Set mode:
% 'all'  -> process all CSV files in folder
% 'list' -> process only specific files listed below
mode = "list";  

% THESE SPECIFIC FILES WILL ONLY BE PLOTTED IF mode = "list" 
% OTHERWISE, THIS IS IGNORED 
file_names = { "2026-03-27 - X-Band Horn - Hcut", "2026-03-27 - X-Band Horn - Vcut" };  
%file_names = { "2026-03-27 - X-Band Horn - Hcut", "2026-03-27 - X-Band Horn - Vcut" };  

% Desired frequencies to plot for each file
target_freqs = [7, 8, 9, 10, 11, 12]; 

% Apply shift to angles 
Hcut_angle_offset = 0; 
Vcut_angle_offset = 90; 

% =========================================================================
% Locate files
% =========================================================================
if mode == "all"
    % All CSV files
    files = dir(fullfile(files_dir, "*" + file_ext));
elseif mode == "list"
    % Specific files
    files = [];
    for k = 1:length(file_names)
        fname = strtrim(file_names{k}) + file_ext;
        f = dir(fullfile(files_dir, fname));
        if isempty(f)
            warning("File '%s' not found in %s", fname, files_dir);
        else
            files = [files; f]; 
        end
    end
else
    error("Invalid mode. Choose 'all' or 'list'.");
end

% Error if no files found
if isempty(files)
    error("No files found to process in %s", files_dir);
end

% Display selected files
disp("Files to process:");
for k = 1:length(files)
    disp(files(k).name)
end

% =========================================================================
% Plot Radiation Patterns
% =========================================================================
import_plot_fonts(); 
define_polar_plot_colors(); 
linewidth = 2; 

for k = 1:length(files)
    % Load CSV file
    data_path = fullfile(files_dir, files(k).name);
    data = readmatrix(data_path);
    
    phi   = data(:,1);
    theta = data(:,2);  
    freq  = data(:,3); 
    gain  = data(:,4); 

    if contains(files(k).name, "Hcut")
        angles = wrapTo180(phi - Hcut_angle_offset); 
        xlabel_str = "\phi (^\circ)"; 
    end

    if contains(files(k).name, "Vcut")
        angles = wrapTo180(theta - Vcut_angle_offset); 
        xlabel_str = "\theta (^\circ)"; 
    end
    
    figure(Position=[100, 100, 1500, 600]); 
    global_max = -inf; 
    global_min = inf; 
    
    % Loop through target frequencies
    for n = 1:length(target_freqs)
        
        % Find nearest frequency in the data
        [~, idx] = min(abs(freq - target_freqs(n)));
        nearest_freq = freq(idx);

        freq_mask = (freq == nearest_freq); 
        
        angle_vect = angles(freq_mask); 
        gain_vect  = gain(freq_mask);

        [angle_vect, sort_idx] = sort(angle_vect);
        gain_vect = gain_vect(sort_idx);

        global_min = min(global_min, min(gain_vect)); 
        global_max = max(global_max, max(gain_vect)); 
        
        sgtitle(files(k).name, Interpreter="none", FontWeight="bold", FontSize=20);

        % Rectangular Plot 
        subplot(1,2,1); 
        plot(angle_vect, gain_vect, LineWidth=linewidth,...
             DisplayName=sprintf("%.1f GHz", nearest_freq)); 
        plot_settings(xlabel_str); 
        hold on; 
        
        % Polar Plot
        subplot(1,2,2); 
        polarplot(deg2rad(angle_vect), gain_vect, LineWidth=linewidth,...
             DisplayName=sprintf("%.1f GHz", nearest_freq));  
        rlim([global_min, global_max]); 

        pax = gca; 
        pax.ColorOrder = get(groot, 'defaultAxesColorOrder');
        hold on;
    end
end

function import_plot_fonts()

    fontName = 'Times New Roman';  
    fontSize = 20; 
    
    % Set font families
    set(groot, 'defaultTextFontName', fontName);
    set(groot, 'defaultAxesFontName', fontName);
    set(groot, 'defaultLegendFontName', fontName);
    set(groot, 'defaultUicontrolFontName', fontName);
    
    % Font sizes
    set(groot, 'defaultAxesFontSize', fontSize);
    set(groot, 'defaultTextFontSize', fontSize);
    set(groot, 'defaultLegendFontSize', fontSize);
    
    % Set interpreter ('latex', 'tex', 'none')
    set(groot, 'defaultTextInterpreter', 'tex');
    set(groot, 'defaultAxesTickLabelInterpreter', 'tex');
    set(groot, 'defaultLegendInterpreter', 'tex');

    % Polar axes
    set(groot, 'defaultPolarAxesFontName', fontName);
    set(groot, 'defaultPolarAxesFontSize', fontSize);
    set(groot, 'defaultPolarAxesLineWidth', 1);   
    set(groot, 'defaultPolarAxesThetaZeroLocation', 'top'); 
    set(groot, 'defaultPolarAxesThetaDir', 'clockwise');   
    
    % Colours from pyvista.org
    mycolors_hex = [
        "#4682b4"; % steelblue
        "#ff6347"; % tomato
        "#00c957"; % emeraldgreen
        "#ffb00f"; % lightcadmiumyellow
        "#ba55d3"; % mediumpurple
        "#48d1cc"; % turqoise
        "#ff69b4"; % hotpink
    ];

    % Convert to RGB
    mycolors = zeros(size(mycolors_hex,1), 3);
    for i = 1:length(mycolors_hex)
        mycolors(i,:) = hex2rgb(mycolors_hex(i));
    end

    set(groot, 'defaultAxesColorOrder', mycolors);

end

function plot_settings(xlabel_str)
    % Plot Settings
    xlabel(xlabel_str, Interpreter="tex"); 
    ylabel("Gain (dB)"); 

    xlim([-180, 180]); 

    ax = gca;
    ax.Box = 'on'; 
    ax.XAxis.MinorTick = 'on';
    ax.YAxis.MinorTick = 'on';
    ax.TickLength = [0.02 0.02]; 

    legend()
end

function define_polar_plot_colors()
% Colours from pyvista.org
    mycolors_hex = [
        "#4682b4"; % steelblue
        "#ff6347"; % tomato
        "#00c957"; % emeraldgreen
        "#ffb00f"; % lightcadmiumyellow
        "#ba55d3"; % mediumpurple
        "#48d1cc"; % turqoise
        "#ff69b4"; % hotpink
    ];

    % Convert to RGB
    mycolors = zeros(size(mycolors_hex,1), 3);
    for i = 1:length(mycolors_hex)
        mycolors(i,:) = hex2rgb(mycolors_hex(i));
    end
end
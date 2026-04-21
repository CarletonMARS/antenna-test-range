clc; clear; close all;

% =========================================================================
% USER PATH CONFIG
% =========================================================================
files_dir = "Measurement Data/Conical Horn - Phase Center vs Aperture/Calibrated"; 
file_ext  = ".csv"; 

% Angle offsets
Hcut_angle_offset = 0; 
Vcut_angle_offset = 0; 

linewidth = 2;

% =========================================================================
% PLOT SETTINGS (COLORS + FONTS)
% =========================================================================
import_plot_fonts();
mycolors = get_colors(); 

% Convenient handles
myblue   = mycolors(1,:); 
myred    = mycolors(2,:); 
mygreen  = mycolors(3,:); 
myyellow = mycolors(4,:); 

% =========================================================================
% USER CONFIGURATION (CORE CONTROL)
% =========================================================================
plot_count = 0;

% Each row in plot_sets(plot_count).files has the format:
%
% {
%   file_name,   % (string) Name of CSV file (without extension)
%   cut_type,    % (string) "Hcut" → uses phi, "Vcut" → uses theta
%   frequency,   % (scalar) Target frequency in GHz (nearest match is used)
%   legend,      % (string) Legend label for this curve
%   linestyle,   % (string) Line style: "-", "--", ":", "-.", etc.
%   color,       % (RGB vector OR "auto"/[]) → manual color [r g b] or auto cycling
%   sweepType,   % (string) "phi", "theta", or "none"
%   sweepValue   % (scalar or []) Value for phi/theta slice (used if sweepType ≠ "none")
% }
%
% Examples:
% - "auto" or [] for color → automatically cycles through predefined colors
% - sweepType = "none" → no additional slicing (use full Hcut/Vcut data)
% - sweepType = "phi"  → extracts constant-phi cut (phi = sweepValue)
% - sweepType = "theta"→ extracts constant-theta cut (theta = sweepValue)

% % =========================================================
% % Example 1: Hcut vs Vcut
% % =========================================================
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "Title";
% 
% plot_sets(plot_count).files = {
%     "2026-03-27 - X-Band Horn - Hcut", "Hcut", 10, "H-cut (10 GHz)", "-", "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Vcut", "Vcut", 10, "V-cut (10 GHz)", "--", "auto", "none", [];
% };
% 
% % =========================================================
% % Example 2: Multiple frequencies
% % =========================================================
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "Title";
% 
% plot_sets(plot_count).files = {
%     "2026-03-27 - X-Band Horn - Hcut", "Hcut", 8,  "8 GHz",  "-", "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Hcut", "Hcut", 10, "10 GHz", "--", "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Hcut", "Hcut", 12, "12 GHz", ":",  "auto", "none", [];
% };
% 
% % =========================================================
% % Horn: On vs. Off Phase Center
% % =========================================================
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "10 GHz, Hcut";
% 
% plot_sets(plot_count).files = {
%     "Horn - Co-pol - Vcut",            "Hcut", 10, "On Phase Center",    "-",   "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Hcut", "Hcut", 10,  "Off Phase Center",  "-", "auto", "none", [];
% };
% 
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "5 GHz, Vcut";
% 
% plot_sets(plot_count).files = {
%     "Horn - Co-pol - Hcut",            "Vcut", 5, "On Phase Center",    "-",   "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Vcut", "Vcut", 5,  "Off Phase Center",  "-", "auto", "none", [];
% };
% 
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "15 GHz, Vcut";
% 
% plot_sets(plot_count).files = {
%     "Horn - Co-pol - Hcut",            "Vcut", 15, "On Phase Center",    "-",   "auto", "none", [];
%     "2026-03-27 - X-Band Horn - Vcut", "Vcut", 15,  "Off Phase Center",  "-", "auto", "none", [];
% };

% =========================================================
% Example 1: Hcut vs Vcut
% =========================================================

% --- Hcut ---------------------------------------------- %

% % *** 5 GHz *** 
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "5 GHz";
% 
% plot_sets(plot_count).files = {
%     "Phase Center Alignment - Hcut", "Hcut", 5, "Phase Center", "-", "auto", "none", [];
%     "Aperture Alignment - Hcut", "Hcut", 5, "Aperture", "-", "auto", "none", [];
% };
% 
% % *** 10 GHz *** 
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "10 GHz";
% 
% plot_sets(plot_count).files = {
%     "Phase Center Alignment - Hcut", "Hcut", 10, "Phase Center", "-", "auto", "none", [];
%     "Aperture Alignment - Hcut", "Hcut", 10, "Aperture", "-", "auto", "none", [];
% };
% 
% % *** 15 GHz *** 
% plot_count = plot_count + 1;
% plot_sets(plot_count).title = "15 GHz";
% 
% plot_sets(plot_count).files = {
%     "Phase Center Alignment - Hcut", "Hcut", 15, "Phase Center", "-", "auto", "none", [];
%     "Aperture Alignment - Hcut", "Hcut", 15, "Aperture", "-", "auto", "none", [];
% };

% =========================================================================
% MAIN LOOP
% =========================================================================
for p = 1:length(plot_sets)

    figure(Position=[100, 100, 1200, 500]);
    files = plot_sets(p).files;

    global_max = -inf;
    global_min = inf;

    % Color cycling reset per figure
    color_idx = 1;
    num_colors = size(mycolors,1);

    for i = 1:size(files,1)

        % =========================
        % Extract config
        % =========================
        file_name  = files{i,1};
        cut_type   = files{i,2};
        fTarget    = files{i,3};
        lgd        = files{i,4};
        ls         = files{i,5};
        col        = files{i,6};
        sweepType  = files{i,7};
        sweepValue = files{i,8};

        % =========================
        % Load file
        % =========================
        data_path = fullfile(files_dir, file_name + file_ext);

        if ~isfile(data_path)
            warning("File not found: %s", data_path);
            continue;
        end

        data = readmatrix(data_path);

        phi   = data(:,1);
        theta = data(:,2);
        freq  = data(:,3);
        gain  = data(:,4);

        % =========================
        % Frequency selection
        % =========================
        [~, idx] = min(abs(freq - fTarget));
        nearest_freq = freq(idx);

        freq_mask = abs(freq - nearest_freq) < 1e-6;

        phi   = phi(freq_mask);
        theta = theta(freq_mask);
        freq = freq(freq_mask); 
        gain  = gain(freq_mask);
        
        
        % =========================
        % Cut selection
        % =========================
        if cut_type == "Hcut"
            angles = wrapTo180(phi - Hcut_angle_offset);
            xlabel_str = "\phi (^\circ)";
        elseif cut_type == "Vcut"
            angles = wrapTo180(theta - Vcut_angle_offset);
            xlabel_str = "\theta (^\circ)";
        else
            error("Unknown cut type: %s", cut_type);
        end

        % =========================
        % Optional slice
        % =========================
        if sweepType == "phi"
            mask = abs(phi - sweepValue) < 1e-3;
            angles = theta(mask);
            gain   = gain(mask);
            xlabel_str = "\theta (^\circ)";
        elseif sweepType == "theta"
            mask = abs(theta - sweepValue) < 1e-3;
            angles = phi(mask);
            gain   = gain(mask);
            xlabel_str = "\phi (^\circ)";
        end

        % gain = gain - max(gain); 

        % =========================
        % Sort
        % =========================
        [angles, idx_sort] = sort(angles);
        gain = gain(idx_sort);

        if isempty(gain)
            warning("No data after filtering for %s", file_name);
            continue;
        end

        global_min = min(global_min, min(gain));
        global_max = max(global_max, max(gain));

        % =========================
        % COLOR HANDLING (KEY FIX)
        % =========================
        if isempty(col) || (string(col) == "auto")
            this_color = mycolors(color_idx,:);
            
            color_idx = color_idx + 1;
            if color_idx > num_colors
                color_idx = 1;
            end
        else
            this_color = col;
        end

        gain = max(gain, -70); % clip it 

        % =========================
        % RECTANGULAR
        % =========================
        subplot(1,2,1);
        scatter(angles, gain); 
        % plot(angles, gain, ...
        %     'LineStyle', ls, ...
        %     'LineWidth', linewidth, ...
        %     'Color', this_color, ...
        %     'DisplayName', lgd);
        hold on;
        plot_settings(xlabel_str);

        % =========================
        % POLAR
        % =========================
        subplot(1,2,2);
        polarplot(deg2rad(angles), gain, ...
            'LineStyle', ls, ...
            'LineWidth', linewidth, ...
            'Color', this_color, ...
            'DisplayName', lgd);
        hold on;

    end

    % =========================
    % Final formatting
    % =========================
    subplot(1,2,1);
    legend(Location="southwest", Box="on", BackgroundAlpha=0.8, EdgeColor=[185,185,185]/255);

    subplot(1,2,2);
    legend(Location="south", Box="on", BackgroundAlpha=0.8, EdgeColor=[185,185,185]/255);
    r_step_size = 10; 
    rmin = floor(min(gain)/r_step_size)*r_step_size;
    rmax = ceil(max(gain)/r_step_size)*r_step_size;
    rticks(rmin:r_step_size:rmax);
    rlim([rmin rmax]);

    if isfield(plot_sets(p), 'title')
        sgtitle(plot_sets(p).title, ...
            'FontWeight',"bold",'FontSize',20);
    else
        sgtitle(sprintf("Plot Set %d", p), ...
            'FontWeight',"bold",'FontSize',20);
    end

end

% =========================================================================
% FUNCTIONS
% =========================================================================
function import_plot_fonts()

    fontName = 'Times New Roman';  
    fontSize = 20; 
    
    set(groot, 'defaultTextFontName', fontName);
    set(groot, 'defaultAxesFontName', fontName);
    set(groot, 'defaultLegendFontName', fontName);
    
    set(groot, 'defaultAxesFontSize', fontSize);
    set(groot, 'defaultTextFontSize', fontSize);
    set(groot, 'defaultLegendFontSize', fontSize);
    
    set(groot, 'defaultTextInterpreter', 'tex');
    set(groot, 'defaultAxesTickLabelInterpreter', 'tex');
    set(groot, 'defaultLegendInterpreter', 'tex');

    set(groot, 'defaultPolarAxesFontName', fontName);
    set(groot, 'defaultPolarAxesFontSize', fontSize);
    set(groot, 'defaultPolarAxesThetaZeroLocation', 'top'); 
    set(groot, 'defaultPolarAxesThetaDir', 'clockwise');   
end

function mycolors = get_colors()

    mycolors_hex = [
        "#4682b4";
        "#ff6347";
        "#00c957";
        "#ffb00f";
        "#ba55d3";
        "#48d1cc";
        "#ff69b4";
    ];

    mycolors = zeros(size(mycolors_hex,1), 3);
    for i = 1:length(mycolors_hex)
        mycolors(i,:) = hex2rgb(mycolors_hex(i));
    end
end

function plot_settings(xlabel_str)

    xlabel(xlabel_str);
    ylabel("Gain (dB)");

    xlim([-180, 180]);

    ax = gca;
    ax.Box = 'on';
    ax.XAxis.MinorTick = 'on';
    ax.YAxis.MinorTick = 'on';
    ax.TickLength = [0.02 0.02];

end
% ========================================================================
% MATLAB script to plot 2D radiation patterns overlaid for multiple files
% ========================================================================

clear; clc; close all;

% Target Frequency to plot
% The csv file may not contain the exact frequency, but the script tries to
% ... plot the closest one
target_freqs = 2:2:18; % (GHz)

folder = "Measurement Data"; 

VPol_files = ["VPol E-Plane", "VPol H-Plane"]; 
HPol_files = ["HPol E-Plane", "HPol H-Plane"]; 

legend_entries = ["E-Plane", "H-Plane"]; % should equal length of VPol_Files (and HPol)

file_ext = ".csv"; 

VPol_file_list = fullfile(folder, VPol_files) + file_ext; 
HPol_file_list = fullfile(folder, HPol_files) + file_ext; 

normalize_data = false; 

% Plot Settings 
linewidth = 2; 
fontname = "Times"; 
fontsize = 16; 
fontsize_ticks = 12; 

fig_width = 28; 
fig_height = 10;

plot_cols = 5; 
plot_rows = ceil(length(target_freqs) / plot_cols);

%% Plot VPol Data
plot_idx = 1; 

fig = figure;
tiledlayout(plot_rows, plot_cols, 'TileSpacing','compact','Padding','compact');

for j=1:length(target_freqs)
    nexttile; 
    hold on; 

    for i=1:length(VPol_file_list)
        fprintf("Plotting VPol data...\n")
        fprintf("File name: %s\n", VPol_file_list(i));
    
        VPol_data = readmatrix(VPol_file_list(i)); 
        
        VPol_phi = VPol_data(:,1); 
        VPol_theta = VPol_data(:,2); 
        VPol_freq = VPol_data(:,3); 
        VPol_mag = VPol_data(:,4); 
    
        % Find the closest frequency to the target
        [~, idx] = min(abs(VPol_freq - target_freqs(j))); 
        freq = VPol_freq(idx); 
    
        fprintf("Closest frequency: %s\n", num2str(freq)); 
    
        mask = (VPol_freq == freq); 
        mag_dB = VPol_mag(mask); 
    
        if contains(VPol_files(i), "E-Plane")
            angle_sweep = VPol_theta(mask);
            angle_sweep = mod(angle_sweep - 90, 360);  
        elseif contains(VPol_files(i), "H-Plane")
            angle_sweep = VPol_phi(mask);
        end
        
        % Wrap angle values to +/- 180 deg
        % Shift + wrap to [-180, 180]
        angle_sweep(angle_sweep > 180) = angle_sweep(angle_sweep > 180) - 360;
        [angle_sweep_sorted, sort_idx] = sort(angle_sweep);
        mag_dB_sorted = mag_dB(sort_idx);

        if normalize_data == true
            mag_dB_sorted = mag_dB_sorted - max(mag_dB_sorted);
        end
        
        plot(angle_sweep_sorted, mag_dB_sorted, DisplayName=legend_entries(i), LineWidth=linewidth); 
    end
    
    % Plot settings
    sgtitle("Co-Pol (V-Pol) Patterns", FontName=fontname, FontSize=fontsize, FontWeight="bold");
    title(freq + " GHz");
    xlabel("Angle (°)");
    ylabel("S_{21} (dB)", Interpreter="tex");
    xlim([-180, 180]);
    xticks(-180:90:180);
    
    legend(Location="south", FontSize=fontsize, Box="off");
    box on;
    
    set(gca, LineWidth=1.2, FontName=fontname, FontSize=fontsize_ticks); 
    ax = gca; 
    ax.Box = 'on'; 
    ax.XMinorTick = 'on'; 
    ax.YMinorTick = 'on';
    ax.TickLength = [0.02, 0.02];
    
    axis square; 

    plot_idx = plot_idx + 1; 
end

%% Plot HPol Data
plot_idx = 1; 

figure;
tiledlayout(plot_rows, plot_cols, TileSpacing="compact", Padding="compact");

for j=1:length(target_freqs)
    nexttile; 
    hold on; 

    for i=1:length(HPol_file_list)
        fprintf("Plotting HPol data...\n")
        fprintf("File name: %s\n", HPol_file_list(i));
    
        HPol_data = readmatrix(HPol_file_list(i)); 
        
        HPol_phi = HPol_data(:,1); 
        HPol_theta = HPol_data(:,2); 
        HPol_freq = HPol_data(:,3); 
        HPol_mag = HPol_data(:,4); 
    
        % Find the closest frequency to the target
        [~, idx] = min(abs(HPol_freq - target_freqs(j))); 
        freq = HPol_freq(idx); 
    
        fprintf("Closest frequency: %s\n", num2str(freq)); 
    
        mask = (HPol_freq == freq); 
        mag_dB = HPol_mag(mask); 
    
        if contains(HPol_files(i), "E-Plane")
            angle_sweep = HPol_theta(mask);
            angle_sweep = mod(angle_sweep - 90, 360);  
        elseif contains(HPol_files(i), "H-Plane")
            angle_sweep = HPol_phi(mask);
        end
        
        % Wrap angle values to +/- 180 deg
        angle_sweep(angle_sweep > 180) = angle_sweep(angle_sweep > 180) - 360;
        [angle_sweep_sorted, sort_idx] = sort(angle_sweep);
        mag_dB_sorted = mag_dB(sort_idx);

        if normalize_data == true
            mag_dB_sorted = mag_dB_sorted - max(mag_dB_sorted);
        end
        
        plot(angle_sweep_sorted, mag_dB_sorted, DisplayName=legend_entries(i), LineWidth=linewidth); 
    end
    
    % Plot settings
    sgtitle("Cross-Pol (H-Pol) Patterns", FontName=fontname, FontSize=fontsize, FontWeight="bold");
    title(freq + " GHz");
    xlabel("Angle (°)");
    ylabel("S_{21} (dB)", Interpreter="tex");
    xlim([-180, 180]);
    xticks(-180:90:180);
    
    legend(Location="south", FontSize=fontsize, Box="off");
    box on;
    
    set(gca, LineWidth=1.2, FontName=fontname, FontSize=fontsize_ticks); 
    ax = gca; 
    ax.Box = 'on'; 
    ax.XMinorTick = 'on'; 
    ax.YMinorTick = 'on';
    ax.TickLength = [0.02, 0.02];
    
    axis square; 

    plot_idx = plot_idx + 1; 
end







clear; clc; close all;

% Target frequencies
target_freqs = 2:0.2:20; % (GHz)

folder = "Measurement Data"; 

VPol_files = ["VPol E-Plane", "VPol H-Plane"]; 
HPol_files = ["HPol E-Plane", "HPol H-Plane"]; 

legend_entries = ["E-Plane", "H-Plane"]; % should equal length of VPol_files / HPol_files

file_ext = ".csv"; 
VPol_file_list = fullfile(folder, VPol_files) + file_ext; 
HPol_file_list = fullfile(folder, HPol_files) + file_ext; 

% Plot Settings
linewidth = 2; 
fontname = "Times"; 
fontsize = 18; 
fontsize_ticks = 14;
fontsize_lgd = 16; 

% Preallocate arrays for maxima
VPol_max = zeros(length(VPol_file_list), length(target_freqs));
HPol_max = zeros(length(HPol_file_list), length(target_freqs));

%% Process VPol files
for j = 1:length(VPol_file_list)
    fprintf("Processing file: %s\n", VPol_file_list(j));
    data = readmatrix(VPol_file_list(j));
    freq  = data(:,3);
    mag   = data(:,4);

    for k = 1:length(target_freqs)
        [~, idx] = min(abs(freq - target_freqs(k)));
        freq_closest = freq(idx);

        mask = (freq == freq_closest);
        mag_at_freq = mag(mask);

        VPol_max(j,k) = max(mag_at_freq);
    end
end

%% Process HPol files
for j = 1:length(HPol_file_list)
    fprintf("Processing file: %s\n", HPol_file_list(j));
    data = readmatrix(HPol_file_list(j));
    freq  = data(:,3);
    mag   = data(:,4);

    for k = 1:length(target_freqs)
        [~, idx] = min(abs(freq - target_freqs(k)));
        freq_closest = freq(idx);

        mask = (freq == freq_closest);
        mag_at_freq = mag(mask);

        HPol_max(j,k) = max(mag_at_freq);
    end
end

%% Plotting
figure;

t = tiledlayout(1,2, 'TileSpacing','compact','Padding','compact');

% --- VPol plot ---
nexttile;
hold on;
for j = 1:length(VPol_file_list)
    plot(target_freqs, VPol_max(j,:), DisplayName=legend_entries(j), LineWidth=linewidth);
end
xlabel("Frequency (GHz)");
ylabel("Max S_{21} (dB)", Interpreter="tex");
title("Co-Pol (VPol)", Interpreter="tex");
legend(Location="best", Box="off", FontSize=fontsize_lgd);
box on;

xlim([min(target_freqs), max(target_freqs)]);

set(gca, LineWidth=1.2, FontName=fontname, FontSize=fontsize_ticks);
ax = gca;
ax.Box = 'on';
ax.XMinorTick = 'on';
ax.YMinorTick = 'on';
ax.TickLength = [0.02, 0.02];
hold off;


% --- HPol plot ---
nexttile;
hold on;
for j = 1:length(HPol_file_list)
    plot(target_freqs, HPol_max(j,:), DisplayName=legend_entries(j), LineWidth=linewidth);
end
xlabel("Frequency (GHz)");
ylabel("Max S_{21} (dB)", Interpreter="tex");
title("Cross-Pol (HPol)", Interpreter="tex");
legend(Location="best", Box="off", FontSize=fontsize_lgd);
box on;

xlim([min(target_freqs), max(target_freqs)]);

set(gca, LineWidth=1.2, FontName=fontname, FontSize=fontsize_ticks);
ax = gca;
ax.Box = 'on';
ax.XMinorTick = 'on';
ax.YMinorTick = 'on';
ax.TickLength = [0.02, 0.02];
hold off;

sgtitle("Peak S_{21} vs Frequency", FontName=fontname, FontSize=fontsize, FontWeight="bold");
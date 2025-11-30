clc; close all; clear all; 

data_folder_path = "Measurement Data"; 
file_extension = "*.s2p"; % ".csv"

%data_files = dir(fullfile(data_folder_path, file_extension));
data_files = ["S-Params - Horn 1 (Tx).s2p", "S-Params - Horn 2 (Rx).s2p"];
num_files = length(data_files); 

% Plotting Parameters
plot_linewidth = 2.5;
plot_linestyles = ["-", "-", "-", "-"];

fontname = "Times"; 
fontsize = 14;
title_font_size = 16;
% set(groot, DefaultTextInterpreter="latex", DefaultTextFontSize=18);
% set(groot, DefaultLegendInterpreter="latex", DefaultLegendFontSize=14);
% set(groot, DefaultAxesTickLabelInterpreter="latex", DefaultAxesFontSize=14);

for i = 1:length(data_files)
    file_path = fullfile(data_folder_path, data_files(i));
    [~, file_name, ~] = fileparts(file_path); % Extract filename without extension
    s_params = sparameters(file_path); 

    freq = s_params.Frequencies;
    freq = freq/1e9; % convert to GHz
    S = s_params.Parameters; 
    S11 = squeeze(S(1,1,:)); 
    S21 = squeeze(S(2,1,:)); 
    S12 = squeeze(S(1,2,:)); 
    S22 = squeeze(S(2,2,:)); 

    S11_dB = 20*log10(abs(S11));
    S21_dB = 20*log10(abs(S21));
    S12_dB = 20*log10(abs(S12));
    S22_dB = 20*log10(abs(S22));

    S11_phase = angle(S11) * (180/pi);
    S21_phase = angle(S21) * (180/pi);
    S12_phase = angle(S12) * (180/pi);
    S22_phase = angle(S22) * (180/pi);

    S11_phase_unwrapped = unwrap(S11_phase); 
    S21_phase_unwrapped = unwrap(S21_phase);
    S12_phase_unwrapped = unwrap(S12_phase);
    S22_phase_unwrapped = unwrap(S22_phase);

    port_counter = 1; 
    S11_display_name = sprintf("$S_{%s%s}$", num2str(port_counter), num2str(port_counter));
    S21_display_name = sprintf("$S_{%s%s}$", num2str(port_counter)+1, num2str(port_counter));
    S12_display_name = sprintf("$S_{%s%s}$", num2str(port_counter), num2str(port_counter)+1);
    S22_display_name = sprintf("$S_{%s%s}$", num2str(port_counter)+1, num2str(port_counter)+1);
    
    figure;

    % Plot S-params Magnitude (dB)
    hold on; 
    plot(freq,S11_dB, LineWidth=plot_linewidth, LineStyle=plot_linestyles(1), DisplayName=S11_display_name);
    plot(freq,S21_dB, LineWidth=plot_linewidth, LineStyle=plot_linestyles(2), DisplayName=S21_display_name);
    plot(freq,S12_dB, LineWidth=plot_linewidth, LineStyle=plot_linestyles(3), DisplayName=S12_display_name);
    plot(freq,S22_dB, LineWidth=plot_linewidth, LineStyle=plot_linestyles(4), DisplayName=S22_display_name);
    hold off;

    title(file_name, FontSize=title_font_size);
    xlabel("Frequency (GHz)", Interpreter="latex");
    ylabel("S-Parameters (dB)", Interpreter="latex");
    legend(Location="best", Interpreter="latex", Box="off");

    xlim([min(freq), max(freq)]);

    % Plot S-Params Phase (Degrees)
    % figure;
    % plot(freq, S11_phase, LineWidth=plot_linewidth, LineStyle=plot_linestyles(1), DisplayName="$S_{11}$");
    % hold on;
    % plot(freq, S21_phase, LineWidth=plot_linewidth, LineStyle=plot_linestyles(2), DisplayName="$S_{21}$");
    % plot(freq, S12_phase, LineWidth=plot_linewidth, LineStyle=plot_linestyles(3), DisplayName="$S_{12}$");
    % plot(freq, S22_phase, LineWidth=plot_linewidth, LineStyle=plot_linestyles(4), DisplayName="$S_{22}$");
    % hold off; 
    % 
    % title(data_files(i).name + " (Phase)", FontName="Times");
    % xlabel("Frequency [GHz]");
    % ylabel("Phase [Degrees]");
    % legend(Location="northeastoutside");

    % Optional
    % Enable minor ticks
    set(gca, FontName=fontname, FontSize=fontsize)
    ax = gca; % Get current axes
    ax.XMinorTick = 'on'; % Enable minor ticks on x-axis
    ax.YMinorTick = 'on'; % Enable minor ticks on y-axis
    % Set major tick length (same for x and y in 2D)
    ax.TickLength = [0.02, 0]; % [2D length, 3D length];
    ax.Box = "on";

    ax.FontSize = fontsize;
    ax.XAxis.TickLabelInterpreter = "latex";
    ax.YAxis.TickLabelInterpreter = "latex";

end

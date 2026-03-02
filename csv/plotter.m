% Load CSV, preserve original variable names exactly
data = readtable('testreal.csv', 'VariableNamingRule', 'preserve');

% Pick frequency to plot
freqToPlot = 2.44; % GHz

% Filter data for that frequency (allowing a small tolerance)
freqTolerance = 0.001;
idx = abs(data.('Frequency (GHz)') - freqToPlot) < freqTolerance;

theta_deg = data.('Theta (deg)')(idx);
phi_deg = data.('Phi (deg)')(idx);
mag_db = data.('Magnitude (dB)')(idx);

% Convert degrees to radians
theta = deg2rad(theta_deg);
phi = deg2rad(phi_deg);

% Convert dB magnitude to linear scale for radius
mag_linear = 10.^(mag_db / 20);


% Or shift so minimum radius is zero
r = mag_db - min(mag_db);  % shift so min radius = 0

% Convert spherical to cartesian
x = r .* sin(theta) .* cos(phi);
y = r .* sin(theta) .* sin(phi);
z = r .* cos(theta);

% Plot
figure('Renderer','opengl');
scatter3(x, y, z, 36, mag_db, 'filled')
colormap(jet)
colorbar
title(['3D Polar Plot with radius = dB magnitude at ', num2str(freqToPlot), ' GHz'])
xlabel('X')
ylabel('Y')
zlabel('Z')
axis equal
grid on
view(45,30)

% Select φ = 0° slice (or closest)
target_phi = 0;
phi_tol = 0.1;  % Tolerance in degrees
slice_idx = abs(phi_deg - target_phi) < phi_tol;

theta_slice = theta_deg(slice_idx);
mag_slice = mag_db(slice_idx);

% Convert to polar
theta_rad = deg2rad(theta_slice);
r = mag_slice - max(mag_slice);  % Normalize if needed (optional)

% Plot
figure;
polarplot(theta_rad, r, 'bo', 'LineWidth', 2)
title(['Elevation Cut at \phi = ', num2str(target_phi), '°'])
rticks([-70 -60 -50 -40]) 
thetaticks(0:30:360)
set(gca, 'ThetaZeroLocation', 'top', 'ThetaDir', 'clockwise')

% Select θ = 90° slice (or closest)
target_theta = 90;
theta_tol = 0.1;
slice_idx = abs(theta_deg - target_theta) < theta_tol;

phi_slice = phi_deg(slice_idx);
mag_slice = mag_db(slice_idx);

% Convert to polar
phi_rad = deg2rad(phi_slice);
r = mag_slice - max(mag_slice);  % Normalize

% Plot
figure;
polarplot(phi_rad, r, 'r', 'LineWidth', 2)
title(['Azimuth Cut at \theta = ', num2str(target_theta), '°'])
rticks([-70 -60 -50 -40])
thetaticks(0:45:180)
set(gca, 'ThetaZeroLocation', 'top', 'ThetaDir', 'clockwise')


% --- Prepare data ---
theta = deg2rad(theta_deg);
phi = deg2rad(phi_deg);
mag_db = mag_db(:);

% Shift dB to make radius positive
r_shifted = mag_db - min(mag_db);

% --- Interpolation grid ---
thetaq = linspace(0, pi, 90);      % theta from 0° to 180°
phiq   = linspace(0, 2*pi, 360);   % phi from 0° to 360°
[PHI, THETA] = meshgrid(phiq, thetaq);

% Interpolate both radius and color
F_r = scatteredInterpolant(phi, theta, r_shifted, 'natural', 'none');
F_color = scatteredInterpolant(phi, theta, mag_db, 'natural', 'none');

R = F_r(PHI, THETA);         % Interpolated radius
C = F_color(PHI, THETA);     % Interpolated color (dB)

% Clean NaNs
R(isnan(R)) = 0;
C(isnan(C)) = min(mag_db);  % Color fallback

% --- Convert to Cartesian coordinates ---
X = R .* sin(THETA) .* cos(PHI);
Y = R .* sin(THETA) .* sin(PHI);
Z = R .* cos(THETA);

% --- Plot surface with color by dB ---
figure('Renderer','opengl');
surf(X, Y, Z, C, 'EdgeColor', 'none', 'FaceAlpha', 0.95);
colormap(jet)
colorbar
caxis([min(mag_db), max(mag_db)])  % Optional: control color scaling
xlabel('X'); ylabel('Y'); zlabel('Z')
title(['3D Interpolated Pattern (dB-colored), ', num2str(freqToPlot), ' GHz'])
axis equal
grid on
view(45,30)

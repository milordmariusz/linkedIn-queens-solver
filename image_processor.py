import cv2
import numpy as np
from scipy import stats
import math

def sort_corners(corners, row_count):
    if not isinstance(corners, list):
        corners = [c for c in corners]

    corners_flat = [corner.ravel() for corner in corners if corner is not None and corner.size > 0]
    if not corners_flat:
        return None, f"Error: No valid corners found after filtering."

    corners_flat = sorted(corners_flat, key=lambda point: (point[1], point[0]))

    expected_corner_count = row_count * row_count
    if len(corners_flat) != expected_corner_count:
        possible_dim = int(math.sqrt(len(corners_flat)))
        if possible_dim >= 2:
            row_count = possible_dim
            expected_corner_count = row_count * row_count
            corners_flat = corners_flat[:expected_corner_count]
            print(f"Warning: Found {len(corners)} corners, adjusting grid to {row_count}x{row_count}.")
            corners_flat = sorted(corners_flat, key=lambda point: (point[1], point[0]))
        else:
            return None, f"Error: Expected a square number of corners, but found {len(corners_flat)}. Cannot form grid."


    points_per_row = row_count

    rows = []
    try:
        for i in range(row_count):
            row_corners = corners_flat[i * points_per_row:(i + 1) * points_per_row]
            if len(row_corners) != points_per_row:
                 raise ValueError(f"Incorrect number of points for row {i}")
            rows.append(sorted(row_corners, key=lambda point: point[0]))
    except Exception as e:
        return None, f"Error during corner sorting into rows: {e}"

    final_rows = []
    for row in rows:
        final_rows.append([(int(p[0]), int(p[1])) for p in row])

    try:
         if not all(len(r) == row_count for r in final_rows):
              return None, "Error: Inconsistent number of corners per row after sorting."
         return np.array(final_rows, dtype=np.int32), None
    except Exception as e:
         return None, f"Error converting sorted corners to NumPy array: {e}"


def colors_are_similar(color1, color2, tolerance):
    c1 = np.array(color1, dtype=np.float64)
    c2 = np.array(color2, dtype=np.float64)
    if c1.shape != c2.shape:
        return False
    return np.all(np.abs(c1 - c2) <= tolerance)

def get_mean_color(image, x, y, size):
    img_h, img_w = image.shape[:2]
    half_size = size // 2

    x, y = int(x), int(y)

    y_start = max(0, y - half_size)
    y_end = min(img_h, y + half_size + 1)
    x_start = max(0, x - half_size)
    x_end = min(img_w, x + half_size + 1)

    region = image[y_start:y_end, x_start:x_end]

    if region.size == 0:
        if 0 <= y < img_h and 0 <= x < img_w:
             pixel_color = image[y, x]
             return tuple(map(float, pixel_color))
        else:
             return (0.0, 0.0, 0.0)

    mean_color = np.mean(region, axis=(0, 1))
    return tuple(mean_color)


def is_safe_for_star(r, c, current_star_positions, occupied_cols, used_numbers, num_grid):
    grid_size = len(num_grid)
    if not (0 <= r < grid_size and 0 <= c < grid_size): return False
    if c in occupied_cols: return False
    number = num_grid[r][c]
    if number in used_numbers: return False
    for star_r, star_c in current_star_positions:
        if abs(r - star_r) <= 1 and abs(c - star_c) <= 1:
            return False
    return True

def solve_stars_recursive(row, current_star_positions, occupied_cols, used_numbers, num_grid):
    grid_size = len(num_grid)
    if row == grid_size:
        return True

    for col in range(grid_size):
        if is_safe_for_star(row, col, current_star_positions, occupied_cols, used_numbers, num_grid):
            number = num_grid[row][col]

            current_star_positions.append((row, col))
            occupied_cols.add(col)
            used_numbers.add(number)

            if solve_stars_recursive(row + 1, current_star_positions, occupied_cols, used_numbers, num_grid):
                return True
            
            last_pos = current_star_positions.pop()
            occupied_cols.remove(last_pos[1])
            used_numbers.remove(number)
            
    return False

def is_almost_square(pts, tolerance=0.25):
    """
    pts: 4 punkty kwadratu w kolejności [pt1, pt2, pt3, pt4]
    tolerance: dopuszczalne odchylenie od proporcji 1:1
    """
    def distance(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    w1 = distance(pts[0], pts[1])
    w2 = distance(pts[2], pts[3])
    h1 = distance(pts[1], pts[2])
    h2 = distance(pts[3], pts[0])

    width = (w1 + w2) / 2
    height = (h1 + h2) / 2

    if height == 0 or width == 0:
        return False

    ratio = width / height
    return (1 - tolerance) <= ratio <= (1 + tolerance)

def process_image(image_data):
    try:
        nparr = np.frombuffer(image_data, np.uint8)
        img_original = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_original is None:
            return None, "Error: Could not decode image data. Is it a valid image format?"

        h, w = img_original.shape[:2]

        sample_size = min(10, h // 4, w // 4)
        if sample_size <= 0:
            return None, "Error: Image too small for background sampling."

        corners_regions = [
            img_original[0:sample_size, 0:sample_size],
            img_original[0:sample_size, w-sample_size:w],
            img_original[h-sample_size:h, 0:sample_size],
            img_original[h-sample_size:h, w-sample_size:w]
        ]
        valid_corners_regions = [c for c in corners_regions if c is not None and c.size > 0]
        if not valid_corners_regions:
             return None, "Error: Could not sample valid corner regions for background."

        sampled_pixels = np.vstack([corner.reshape(-1, 3) for corner in valid_corners_regions])
        if sampled_pixels.size == 0:
             return None, "Error: No pixels sampled for background estimation."

        try:
            mode_result = stats.mode(sampled_pixels, axis=0, keepdims=True)
            bg_color_mode = mode_result.mode.flatten().astype(np.uint8) if hasattr(mode_result, 'mode') else mode_result[0].flatten().astype(np.uint8)
        except Exception as e:
             return None, f"Error calculating background color: {e}"

        bg_color = bg_color_mode
        color_tolerance = 40

        diff_b = cv2.absdiff(img_original[:, :, 0], int(bg_color[0]))
        diff_g = cv2.absdiff(img_original[:, :, 1], int(bg_color[1]))
        diff_r = cv2.absdiff(img_original[:, :, 2], int(bg_color[2]))
        mask_b = (diff_b > color_tolerance).astype(np.uint8) * 255
        mask_g = (diff_g > color_tolerance).astype(np.uint8) * 255
        mask_r = (diff_r > color_tolerance).astype(np.uint8) * 255
        mask_combined_bg = cv2.bitwise_or(mask_b, mask_g)
        mask_uint8 = cv2.bitwise_or(mask_combined_bg, mask_r)

        kernel_size = 5
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        mask_closed = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask_opened = cv2.morphologyEx(mask_closed, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask_opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        board_to_process = None
        if contours:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            board_contour = contours[0]
            x, y, w_box, h_box = cv2.boundingRect(board_contour)

            margin = 2
            x_m = max(0, x - margin)
            y_m = max(0, y - margin)
            w_m = min(img_original.shape[1] - x_m, w_box + 2 * margin)
            h_m = min(img_original.shape[0] - y_m, h_box + 2 * margin)

            extracted_board = img_original[y_m:y_m+h_m, x_m:x_m+w_m]

            if extracted_board.size == 0:
                return None, "Error: Extracted board region is empty after contour detection."
            else:
                border_thickness = 5
                lightness_threshold = 150
                avg_intensity = np.mean(bg_color_mode) if bg_color_mode is not None and bg_color_mode.size == 3 else 0

                if avg_intensity < lightness_threshold:
                    board_to_process = cv2.copyMakeBorder(
                        extracted_board, border_thickness, border_thickness, border_thickness, border_thickness,
                        cv2.BORDER_CONSTANT, value=[255, 255, 255]
                    )
                else:
                    board_to_process = extracted_board

        else:
            return None, "Error: Could not find any contours in the foreground mask. Is the board clearly visible?"

        if board_to_process is None or board_to_process.size == 0:
            return None, "Error: Board processing failed (board_to_process is empty)."

        img_for_corners = board_to_process.copy()
        gray = cv2.cvtColor(img_for_corners, cv2.COLOR_BGR2GRAY)

        min_corner_distance_factor = 0.04
        min_dim = min(gray.shape[0], gray.shape[1])
        min_corner_distance = max(10, int(min_dim * min_corner_distance_factor))

        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=100,      
            qualityLevel=0.02,    
            minDistance=min_corner_distance 
        )

        if corners is None or len(corners) < 4:
            return None, f"Error: Not enough corners found ({len(corners) if corners is not None else 0}). Try a clearer image or adjust detection parameters."

        num_corners_found = len(corners)
        grid_dimension_float = math.sqrt(num_corners_found)
        grid_dimension = int(round(grid_dimension_float))

        if abs(grid_dimension * grid_dimension - num_corners_found) > 2 : 
             return None, f"Error: Found {num_corners_found} corners. Expected a number close to a perfect square. Cannot determine grid size."
        elif grid_dimension * grid_dimension != num_corners_found:
             print(f"Warning: Found {num_corners_found} corners, assuming {grid_dimension}x{grid_dimension} grid based on rounding.")

        EXPECTED_ROW_COUNT = grid_dimension
        puzzle_size_N = EXPECTED_ROW_COUNT - 1

        if puzzle_size_N < 1:
             return None, f"Error: Deduced grid size {EXPECTED_ROW_COUNT}x{EXPECTED_ROW_COUNT} is too small for a puzzle."

        print(f"Detected {num_corners_found} corners, proceeding with {EXPECTED_ROW_COUNT}x{EXPECTED_ROW_COUNT} corner grid ({puzzle_size_N}x{puzzle_size_N} puzzle squares).")

        sorted_corners_array, sort_error = sort_corners(corners, EXPECTED_ROW_COUNT)
        if sort_error:
            return None, sort_error
        if sorted_corners_array is None or sorted_corners_array.shape[0] != EXPECTED_ROW_COUNT or sorted_corners_array.shape[1] != EXPECTED_ROW_COUNT:
             return None, "Error: Corner sorting did not return the expected grid structure."

        color_to_number = {}
        next_color_number = 1
        numbers_grid = []
        midpoints_grid = []
        SQUARE_SIZE = max(5, int(min_corner_distance / 4))
        COLOR_TOLERANCE = 15

        num_rows_squares = sorted_corners_array.shape[0] - 1
        num_cols_squares = sorted_corners_array.shape[1] - 1

        for row in range(num_rows_squares):
            row_numbers = []
            row_midpoints = []
            for column in range(num_cols_squares):
                point_tl = sorted_corners_array[row][column]
                point_tr = sorted_corners_array[row][column + 1]
                point_bl = sorted_corners_array[row + 1][column]
                point_br = sorted_corners_array[row + 1][column + 1]

                pts = [tuple(point_tl), tuple(point_tr), tuple(point_bl), tuple(point_br)]

                midpoint_x = int(np.mean([p[0] for p in pts]))
                midpoint_y = int(np.mean([p[1] for p in pts]))
                midpoint_coord = (midpoint_x, midpoint_y)
                row_midpoints.append(midpoint_coord)

                mean_color_tuple = get_mean_color(img_for_corners, midpoint_x, midpoint_y, SQUARE_SIZE)

                found_existing_color = False
                assigned_number = -1
                for existing_color_tuple, number in color_to_number.items():
                    if colors_are_similar(mean_color_tuple, existing_color_tuple, COLOR_TOLERANCE):
                        assigned_number = number
                        found_existing_color = True
                        break

                if not found_existing_color:
                    if not colors_are_similar(mean_color_tuple, tuple(bg_color.astype(float)), COLOR_TOLERANCE * 1.5):
                         assigned_number = next_color_number
                         color_to_number[mean_color_tuple] = next_color_number
                         next_color_number += 1
                    else:
                         assigned_number = 0


                row_numbers.append(assigned_number)

            numbers_grid.append(row_numbers)
            midpoints_grid.append(row_midpoints)

        N = len(numbers_grid)
        if N == 0 or any(len(row) != N for row in numbers_grid):
            return None, "Error: The constructed 'numbers_grid' is empty or not square. Cannot solve."

        print("\nNumbers Grid:")
        for r in numbers_grid:
            print(r)
        print("\nSolving...")

        star_positions = []
        cols_occupied = set()
        numbers_used = set()

        solution_found = solve_stars_recursive(0, star_positions, cols_occupied, numbers_used, numbers_grid)

        if solution_found:
            print(f"Solution found! Star positions (row, col): {star_positions}")
            img_with_stars = img_for_corners.copy()

            invalid_squares = 0
            total_squares = num_rows_squares * num_cols_squares

            for row in range(num_rows_squares):
                for col in range(num_cols_squares):
                    pt1 = tuple(sorted_corners_array[row][col])
                    pt2 = tuple(sorted_corners_array[row][col + 1])
                    pt3 = tuple(sorted_corners_array[row + 1][col + 1])
                    pt4 = tuple(sorted_corners_array[row + 1][col])

                    square_pts = [pt1, pt2, pt3, pt4]

                    if not is_almost_square(square_pts):
                        invalid_squares += 1

            if invalid_squares / total_squares > 0.2:
                raise ValueError("Nie można wykryć poprawnej siatki — upewnij się, że zdjęcie jest dobrze docięte i siatka nie jest zniekształcona.")

            for r, c in star_positions:
                if 0 <= r < len(midpoints_grid) and 0 <= c < len(midpoints_grid[r]):
                    midpoint_x, midpoint_y = midpoints_grid[r][c]
                    dot_color_bgr = (0, 0, 255)
                    cell_w = abs(sorted_corners_array[r][c+1][0] - sorted_corners_array[r][c][0]) if c+1 < sorted_corners_array.shape[1] else 20
                    cell_h = abs(sorted_corners_array[r+1][c][1] - sorted_corners_array[r][c][1]) if r+1 < sorted_corners_array.shape[0] else 20
                    dot_radius = max(3, int(min(cell_w, cell_h) * 0.15))
                    dot_thickness = -1
                    cv2.circle(img_with_stars, (midpoint_x, midpoint_y), dot_radius, dot_color_bgr, dot_thickness)
                else:
                    print(f"Warning: Star position ({r}, {c}) is out of midpoints grid bounds.")

            is_success, buffer = cv2.imencode(".png", img_with_stars)
            if is_success:
                return buffer.tobytes(), None
            else:
                return None, "Error: Failed to encode the result image."

        else:
            return None, "No solution found that satisfies all constraints for the given grid."

    except cv2.error as e:
        return None, f"OpenCV Error: {e}. Check image integrity and processing steps."
    except ValueError as e:
        return None, f"{e}"
    except IndexError as e:
         return None, f"Index Error: {e}. Problem accessing elements in lists or arrays, check grid dimensions."
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return None, f"An unexpected error occurred: {e}"
./magick.exe ./in.png ^
  -alpha set -fuzz 8% ^
  -bordercolor white -border 1 ^
  -fill none -draw "alpha 0,0 floodfill" ^
  -shave 1x1 ^
  ( +clone -alpha extract -threshold 60% -morphology Open Diamond:1 -morphology Close Diamond:1 ) ^
  -write mpr:AMASK +delete ^
  -alpha off -compose CopyOpacity mpr:AMASK -composite ^
  -write mpr:ALPHA_ORIG +delete ^
  mpr:ALPHA_ORIG ^
  ( +clone -alpha extract -morphology EdgeOut Diamond:1 ) -write mpr:OUT1 +delete ^
  ( mpr:ALPHA_ORIG -alpha off -fill black -colorize 100 mpr:OUT1 -compose CopyOpacity -composite ) ^
  -compose Over -composite ^
  -write out_orig.png +delete ^
  mpr:ALPHA_ORIG -filter point -resize 48x48! -write mpr:ALPHA_S +delete ^
  mpr:ALPHA_S ^
  ( +clone -alpha extract -morphology EdgeOut Diamond:1 ) -write mpr:OUT2 +delete ^
  ( mpr:ALPHA_S -alpha off -fill black -colorize 100 mpr:OUT2 -compose CopyOpacity -composite ) ^
  -compose Over -composite ^
  out_48.png

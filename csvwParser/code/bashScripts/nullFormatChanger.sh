#!/bin/bash
all='$0'
arg=$1
file=$2
echo COL:$arg FILE:$file
#cat ./tmp/$file | cut -d ',' -f$col | sed  -r -e "s/,$null,/,null,/"
#echo awk -F'\",\"' '{gsub(/\-/,"null",$5); print $0 }' tmp/gene_info
#awk -F'\",\"' "{gsub(/\\$null/,\"null\",$col); print $all }" tmp/$file 
{ rm tmp/$file && awk -F'\",\"' "{$arg print;}" OFS='\",\"' > tmp/$file; } < tmp/$file


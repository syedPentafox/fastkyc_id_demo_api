let input = [1, 2, 3, 3, 3, 2, 4, 1, 5];  //1,2,3,4,5
        //   0, 1, 2, 3, 4, 5, 6, 7, 8

let Output = []; // => Created Empty Array For Storing Unique Values

for (let i = 0; i < input.length; i++) {
  let word = input[i]; 

  if (!Output[word]) { 
    Output.push(word);
  }
}

console.log(Output);


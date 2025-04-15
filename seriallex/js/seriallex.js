document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    // Display newest BL movies (already sorted by date_added in getMoviesByCategory)
    const blMoviesContainer = document.getElementById('all-movies');
    const blMovies = getMoviesByCategory('seriallex').slice(0, 8);
    blMoviesContainer.innerHTML = blMovies.map(createMovieCard).join('');

});

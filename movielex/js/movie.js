document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    const movieTitle = getUrlParameter('title');
    if (!movieTitle || !movieData[movieTitle]) {
        window.location.href = 'movielex.html';
        return;
    }
    
    const movie = movieData[movieTitle];
    
    // Set movie details - using title_name for display
    document.getElementById('movie-title').textContent = movie.title_name || movie.title;
    document.getElementById('movie-poster').src = movie.poster;
    document.getElementById('movie-poster').alt = movie.title_name || movie.title;
    document.getElementById('movie-year').textContent = movie.year;
    document.getElementById('movie-duration').textContent = movie.duration;
    document.getElementById('movie-rating').textContent = `${movie.rating} ★`;
    document.getElementById('movie-description').textContent = movie.description;
    document.getElementById('movie-cast').textContent = movie.cast;
    document.getElementById('movie-director').textContent = movie.director;
    document.getElementById('movie-release').textContent = movie.release;
    
    // Set genres
    const genresContainer = document.getElementById('movie-genres');
    genresContainer.innerHTML = movie.genre.split(', ').map(genre => 
        `<span>${genre}</span>`
    ).join('');
    
    // Trailer link
    const trailerLink = document.getElementById('trailer-link');
    trailerLink.href = `https://t.me/meme_kino_bot?start=trailer_${encodeURIComponent(movie.title)}`;
    
    // Video player functionality
    const watchBtn = document.getElementById('watch-btn');
    const modal = document.getElementById('video-modal');
    const closeBtn = document.querySelector('.close-btn');
    const videoPlayer = document.getElementById('video-player');
    
    watchBtn.addEventListener('click', () => {
        if (movie.video_source) {
            videoPlayer.src = movie.video_source;
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden'; // Prevent scrolling
        }
    });
    
    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        videoPlayer.src = ''; // Stop video when closing
        document.body.style.overflow = 'auto'; // Enable scrolling
    });
    
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
            videoPlayer.src = ''; // Stop video when clicking outside
            document.body.style.overflow = 'auto'; // Enable scrolling
        }
    });
});
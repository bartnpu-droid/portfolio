<?php
/**
 * Title: Find your scent
 * Slug: ombra/scents
 * Categories: ombra
 * Keywords: scents, fragrance, notes
 * Viewport width: 1400
 *
 * @package Ombra
 */

$ombra_scents = array(
	array(
		'name'  => __( 'Fig & Cedar', 'ombra' ),
		'image' => 'scent-fig.jpg',
		'notes' => __( 'Green fig leaf · fig milk · cedarwood · vetiver', 'ombra' ),
		'text'  => __( 'Green and woody. A garden wall still warm after a summer day.', 'ombra' ),
		'slug'  => 'fig-cedar-candle',
	),
	array(
		'name'  => __( 'Sea Salt & Sage', 'ombra' ),
		'image' => 'scent-salt.jpg',
		'notes' => __( 'Sea salt · wild sage · ambrette · driftwood', 'ombra' ),
		'text'  => __( 'Fresh and airy. Windows open, linen drying, the coast close by.', 'ombra' ),
		'slug'  => 'sea-salt-sage-candle',
	),
	array(
		'name'  => __( 'Amber & Smoke', 'ombra' ),
		'image' => 'scent-amber.jpg',
		'notes' => __( 'Amber resin · smoked birch · tonka · labdanum', 'ombra' ),
		'text'  => __( 'Warm and deep. A fire burning low on a cold night.', 'ombra' ),
		'slug'  => 'amber-smoke-candle',
	),
);
?>
<!-- wp:group {"anchor":"scents","className":"ombra-scents","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|60"},"blockGap":"var:preset|spacing|50"},"elements":{"link":{"color":{"text":"var:preset|color|base"}}}},"backgroundColor":"night","textColor":"base","layout":{"type":"constrained"}} -->
<div id="scents" class="wp-block-group ombra-scents has-base-color has-night-background-color has-text-color has-background has-link-color" style="padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--60)">
<!-- wp:group {"style":{"spacing":{"blockGap":"1rem"}},"layout":{"type":"constrained","contentSize":"640px"}} -->
<div class="wp-block-group">
<!-- wp:paragraph {"align":"center","className":"ombra-eyebrow","textColor":"accent-2"} -->
<p class="has-text-align-center ombra-eyebrow has-accent-2-color has-text-color"><?php esc_html_e( 'Three scents, each in every format', 'ombra' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:heading {"textAlign":"center","level":2} -->
<h2 class="wp-block-heading has-text-align-center"><?php esc_html_e( 'Find your scent', 'ombra' ); ?></h2>
<!-- /wp:heading -->
</div>
<!-- /wp:group -->

<!-- wp:columns {"align":"wide","style":{"spacing":{"blockGap":{"left":"var:preset|spacing|40","top":"var:preset|spacing|50"}}}} -->
<div class="wp-block-columns alignwide">
<?php foreach ( $ombra_scents as $ombra_scent ) : ?>
<!-- wp:column {"className":"ombra-scent","style":{"spacing":{"blockGap":"0.9rem"}}} -->
<div class="wp-block-column ombra-scent">
<!-- wp:image {"aspectRatio":"1","scale":"cover","sizeSlug":"full","linkDestination":"custom","className":"ombra-scent__image"} -->
<figure class="wp-block-image size-full ombra-scent__image"><a href="<?php echo esc_url( ombra_product_url( $ombra_scent['slug'] ) ); ?>"><img src="<?php echo esc_url( ombra_image( $ombra_scent['image'] ) ); ?>" alt="<?php echo esc_attr( sprintf( /* translators: %s: scent name */ __( '%s candle, lit', 'ombra' ), $ombra_scent['name'] ) ); ?>" style="aspect-ratio:1;object-fit:cover"/></a></figure>
<!-- /wp:image -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading"><?php echo esc_html( $ombra_scent['name'] ); ?></h3>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"ombra-notes","textColor":"accent-2","fontSize":"small"} -->
<p class="ombra-notes has-accent-2-color has-text-color has-small-font-size"><?php echo esc_html( $ombra_scent['notes'] ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {"textColor":"base-3"} -->
<p class="has-base-3-color has-text-color"><?php echo esc_html( $ombra_scent['text'] ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {"className":"ombra-link-arrow","fontSize":"small"} -->
<p class="ombra-link-arrow has-small-font-size"><a href="<?php echo esc_url( ombra_product_url( $ombra_scent['slug'] ) ); ?>"><?php echo esc_html( sprintf( /* translators: %s: scent name */ __( 'Shop %s', 'ombra' ), $ombra_scent['name'] ) ); ?></a></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:column -->
<?php endforeach; ?>
</div>
<!-- /wp:columns -->
</div>
<!-- /wp:group -->
